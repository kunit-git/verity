from django.db.models import Prefetch
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.items.models import CustomFieldValue, Item
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.mixins import VaultScopedMixin
from apps.vaults.permissions import HasVaultAccess, VaultNotLocked
from .models import Matrix, MatrixAnnotation, MatrixDisplayColumn, MatrixSource
from .serializers import MatrixSerializer, MatrixWriteSerializer
from .traversal import compute_row_hash, evaluate_formulas, run_traversal


class MatrixViewSet(VaultScopedMixin, viewsets.ModelViewSet):
    permission_classes = [HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked]

    def get_queryset(self):
        return Matrix.objects.select_related("created_by").prefetch_related(
            Prefetch(
                "sources",
                queryset=MatrixSource.objects.select_related(
                    "seed_item_type", "seed_container", "relation_type"
                ),
            ),
            "display_columns",
        ).filter(vault=self.current_vault)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MatrixWriteSerializer
        return MatrixSerializer

    @action(detail=True, methods=["get"], url_path="data")
    def data(self, request, pk=None):
        matrix = self.get_object()
        sources = list(
            MatrixSource.objects.filter(matrix=matrix).select_related(
                "seed_item_type", "seed_container", "relation_type"
            ).order_by("position")
        )

        if not sources:
            return Response({"columns": [], "rows": []})

        seed_src = sources[0]

        # Build seed items
        seed_qs = Item.objects.select_related("item_type").filter(
            item_type=seed_src.seed_item_type
        )
        if seed_src.seed_container:
            comp_types = RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)
            child_ids = ItemRelation.objects.filter(
                relation_type__in=comp_types,
                source=seed_src.seed_container,
            ).values_list("target_id", flat=True)
            seed_qs = seed_qs.filter(id__in=child_ids)

        seed_items = list(seed_qs)

        # Build name-to-source-index map (including seed at index 0)
        name_to_row_idx = {src.name: i for i, src in enumerate(sources)}

        # Convert non-seed sources to generic spec dicts
        non_seed_specs = [
            {
                "kind": src.kind,
                "name": src.name,
                "relation_type_id": str(src.relation_type_id) if src.relation_type_id else None,
                "direction": src.direction,
                "formula": src.formula,
                "source_ref": src.source_ref,
                "field_slug": src.field_slug,
            }
            for src in sources[1:]
        ]

        rows, formula_col_indices, non_traversal_col_indices = run_traversal(
            non_seed_specs, seed_items
        )

        # Evaluate formula columns
        if formula_col_indices:
            seed_spec = {"name": seed_src.name, "kind": "seed"}
            all_specs = [seed_spec] + non_seed_specs
            evaluate_formulas(all_specs, rows, formula_col_indices, non_traversal_col_indices)

        # Compute row hashes for annotation lookup
        annotation_source_names = [
            src.name
            for src in sources
            if src.kind == "annotation"
        ]

        annotation_lookup: dict[tuple, str] = {}
        if annotation_source_names and rows:
            row_hashes = [compute_row_hash(row, non_traversal_col_indices) for row in rows]
            annotations = MatrixAnnotation.objects.filter(
                matrix=matrix,
                column_slug__in=annotation_source_names,
                row_hash__in=row_hashes,
            )
            for ann in annotations:
                annotation_lookup[(ann.column_slug, ann.row_hash)] = ann.value
        else:
            row_hashes = []

        # Resolve item_field sources
        item_field_sources = [
            src for src in sources if src.kind == "item_field"
        ]
        item_field_lookup: dict[tuple, object] = {}
        if item_field_sources and rows:
            for src in item_field_sources:
                ref_idx = name_to_row_idx.get(src.source_ref)
                if ref_idx is None or not src.field_slug:
                    continue
                item_ids = {
                    row[ref_idx].id
                    for row in rows
                    if ref_idx < len(row) and row[ref_idx] is not None and hasattr(row[ref_idx], "id")
                }
                if not item_ids:
                    continue
                cfvs = CustomFieldValue.objects.filter(
                    item_id__in=item_ids,
                    field_definition__slug=src.field_slug,
                ).select_related("field_definition")
                for cfv in cfvs:
                    item_field_lookup[(str(cfv.item_id), src.field_slug)] = cfv.value

        # Load display columns for response ordering
        display_columns = list(
            MatrixDisplayColumn.objects.filter(matrix=matrix).order_by("position")
        )

        def serialize_cell(source_name, row, row_hash):
            src_idx = name_to_row_idx.get(source_name)
            if src_idx is None:
                return None
            src = sources[src_idx]

            if src.kind == "formula":
                cell = row[src_idx] if src_idx < len(row) else None
                return {"value": cell} if cell is not None else None

            if src.kind == "annotation":
                value = annotation_lookup.get((source_name, row_hash), "")
                return {
                    "annotation": True,
                    "value": value,
                    "row_hash": row_hash,
                    "column_slug": source_name,
                }

            if src.kind == "item_field":
                ref_idx = name_to_row_idx.get(src.source_ref)
                source_item = row[ref_idx] if ref_idx is not None and ref_idx < len(row) else None
                if source_item is not None and hasattr(source_item, "id"):
                    value = item_field_lookup.get((str(source_item.id), src.field_slug))
                    return {"item_field": True, "value": value}
                return {"item_field": True, "value": None}

            # seed or traversal
            cell = row[src_idx] if src_idx < len(row) else None
            if cell is None:
                return None
            return {
                "id": str(cell.id),
                "title": cell.title,
                "item_type_name": cell.item_type.name,
                "item_type_slug": cell.item_type.slug,
            }

        serialized_rows = []
        for row_idx, row in enumerate(rows):
            row_hash = row_hashes[row_idx] if row_hashes else compute_row_hash(row, non_traversal_col_indices)
            serialized_rows.append([
                serialize_cell(dc.source_name, row, row_hash)
                for dc in display_columns
            ])

        return Response({
            "columns": [
                {
                    "position": dc.position,
                    "heading": dc.heading,
                    "source": dc.source_name,
                    "kind": sources[name_to_row_idx[dc.source_name]].kind
                    if dc.source_name in name_to_row_idx else None,
                    "slug": dc.source_name
                    if dc.source_name in name_to_row_idx
                    and sources[name_to_row_idx[dc.source_name]].kind == "annotation"
                    else None,
                }
                for dc in display_columns
            ],
            "rows": serialized_rows,
        })

    @action(detail=True, methods=["patch"], url_path="annotate")
    def annotate(self, request, pk=None):
        """Upsert an annotation value for a specific annotation source and row."""
        matrix = self.get_object()

        column_slug = request.data.get("column_slug", "").strip()
        row_hash = request.data.get("row_hash", "").strip()
        value = request.data.get("value", "")

        if not column_slug:
            raise drf_serializers.ValidationError({"column_slug": "This field is required."})
        if not row_hash:
            raise drf_serializers.ValidationError({"row_hash": "This field is required."})

        # Verify the column_slug exists as an annotation source in this matrix
        exists = MatrixSource.objects.filter(
            matrix=matrix,
            kind=MatrixSource.Kind.ANNOTATION,
            name=column_slug,
        ).exists()
        if not exists:
            raise drf_serializers.ValidationError(
                {"column_slug": f"No annotation source with name '{column_slug}' in this matrix."}
            )

        annotation, _ = MatrixAnnotation.objects.update_or_create(
            matrix=matrix,
            column_slug=column_slug,
            row_hash=row_hash,
            defaults={"value": value, "updated_by": request.user},
        )

        return Response({
            "column_slug": annotation.column_slug,
            "row_hash": annotation.row_hash,
            "value": annotation.value,
        })
