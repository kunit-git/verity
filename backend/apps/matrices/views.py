from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.items.models import CustomFieldDefinition, CustomFieldValue, Item
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.mixins import VaultScopedMixin
from apps.vaults.permissions import HasVaultAccess, VaultNotLocked
from .formula import evaluate, extract_references, parse_formula
from .models import Matrix, MatrixColumn
from .serializers import MatrixSerializer, MatrixWriteSerializer


class MatrixViewSet(VaultScopedMixin, viewsets.ModelViewSet):
    permission_classes = [HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked]

    def get_queryset(self):
        return Matrix.objects.select_related("created_by").prefetch_related(
            Prefetch(
                "columns",
                queryset=MatrixColumn.objects.select_related(
                    "seed_item_type", "seed_container", "relation_type"
                ),
            ),
        ).filter(vault=self.current_vault)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MatrixWriteSerializer
        return MatrixSerializer

    @action(detail=True, methods=["get"], url_path="data")
    def data(self, request, pk=None):
        matrix = self.get_object()
        columns = list(
            MatrixColumn.objects.filter(matrix=matrix).select_related(
                "seed_item_type", "seed_container", "relation_type"
            ).order_by("position")
        )

        if not columns:
            return Response({"columns": [], "rows": []})

        seed_col = columns[0]

        # Build seed items
        seed_qs = Item.objects.select_related("item_type").filter(
            item_type=seed_col.seed_item_type
        )
        if seed_col.seed_container:
            comp_types = RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)
            child_ids = ItemRelation.objects.filter(
                relation_type__in=comp_types,
                source=seed_col.seed_container,
            ).values_list("target_id", flat=True)
            seed_qs = seed_qs.filter(id__in=child_ids)

        rows = [[item] for item in seed_qs]

        # Track which column indices are formula columns
        formula_col_indices = set()

        # Pass 1: Traverse relations, insert placeholders for formula columns
        for col_idx, col in enumerate(columns[1:], start=1):
            if col.column_kind == MatrixColumn.Kind.FORMULA:
                formula_col_indices.add(col_idx)
                rows = [row + [None] for row in rows]
                continue

            if not col.relation_type or not col.direction:
                rows = [row + [None] for row in rows]
                continue

            new_rows = []
            for row in rows:
                # Find the most recent non-formula Item cell
                last_item = None
                for i in range(len(row) - 1, -1, -1):
                    if i not in formula_col_indices and row[i] is not None:
                        last_item = row[i]
                        break

                if last_item is None:
                    new_rows.append(row + [None])
                    continue

                if col.direction == MatrixColumn.Direction.OUTGOING:
                    rels = ItemRelation.objects.filter(
                        relation_type=col.relation_type,
                        source=last_item,
                    ).select_related("target", "target__item_type")
                    matched = [r.target for r in rels]
                else:
                    rels = ItemRelation.objects.filter(
                        relation_type=col.relation_type,
                        target=last_item,
                    ).select_related("source", "source__item_type")
                    matched = [r.source for r in rels]

                if matched:
                    for m in matched:
                        new_rows.append(row + [m])
                else:
                    new_rows.append(row + [None])

            rows = new_rows

        # Pass 2: Evaluate formula columns
        if formula_col_indices and rows:
            self._evaluate_formulas(columns, rows, formula_col_indices)

        def serialize_cell(cell, col_idx):
            if col_idx in formula_col_indices:
                if cell is None:
                    return None
                return {"value": cell}
            if cell is None:
                return None
            return {
                "id": str(cell.id),
                "title": cell.title,
                "item_type_name": cell.item_type.name,
                "item_type_slug": cell.item_type.slug,
            }

        return Response({
            "columns": [
                {
                    "position": col.position,
                    "label": col.label,
                    "kind": col.column_kind,
                }
                for col in columns
            ],
            "rows": [
                [serialize_cell(cell, col_idx) for col_idx, cell in enumerate(row)]
                for row in rows
            ],
        })

    def _evaluate_formulas(self, columns, rows, formula_col_indices):
        """Evaluate all formula columns in-place on the rows."""
        for col_idx in sorted(formula_col_indices):
            col = columns[col_idx]
            ast = parse_formula(col.formula)
            refs = extract_references(ast)

            if not refs:
                continue

            # Build a map: display number (1-based) → column index in rows
            # User writes $1 for the first column (position 0), $2 for position 1, etc.
            pos_to_idx = {c.position + 1: i for i, c in enumerate(columns)}

            # Collect all item IDs per referenced column position
            ref_col_positions = {r[0] for r in refs}
            ref_slugs = {r[1] for r in refs}
            item_ids_by_col = {}
            for ref_pos in ref_col_positions:
                idx = pos_to_idx.get(ref_pos)
                if idx is None or idx in formula_col_indices:
                    continue
                ids = set()
                for row in rows:
                    cell = row[idx]
                    if cell is not None and hasattr(cell, "id"):
                        ids.add(cell.id)
                item_ids_by_col[ref_pos] = ids

            # Batch-load custom field values
            all_item_ids = set()
            for ids in item_ids_by_col.values():
                all_item_ids |= ids

            if not all_item_ids:
                continue

            # Load field definitions for the referenced slugs
            field_defs = {
                fd.slug: fd
                for fd in CustomFieldDefinition.objects.filter(slug__in=ref_slugs)
            }

            # Load custom field values
            cfvs = CustomFieldValue.objects.filter(
                item_id__in=all_item_ids,
                field_definition__slug__in=ref_slugs,
            ).select_related("field_definition")

            # Build lookup: (item_id, slug) → raw value
            raw_values = {}
            for cfv in cfvs:
                raw_values[(cfv.item_id, cfv.field_definition.slug)] = cfv.value

            # Evaluate each row
            for row in rows:
                context = {}
                has_missing = False
                for ref_pos, slug in refs:
                    idx = pos_to_idx.get(ref_pos)
                    if idx is None or idx in formula_col_indices:
                        has_missing = True
                        break
                    cell = row[idx]
                    if cell is None or not hasattr(cell, "id"):
                        has_missing = True
                        break
                    raw = raw_values.get((cell.id, slug))
                    numeric = self._to_numeric(raw, field_defs.get(slug))
                    context[(ref_pos, slug)] = numeric

                if has_missing:
                    row[col_idx] = None
                else:
                    row[col_idx] = evaluate(ast, context)

    @staticmethod
    def _to_numeric(raw_value, field_def):
        """Convert a custom field value to a number for formula evaluation."""
        if raw_value is None:
            return None

        # Choice fields: 1-based index in the choices list
        if field_def and field_def.field_kind == "choice":
            choices = (field_def.options or {}).get("choices", [])
            if raw_value in choices:
                return float(choices.index(raw_value) + 1)
            return None

        # Numeric types
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None
