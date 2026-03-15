from django.db.models import BooleanField, Count, Exists, F, Prefetch, Q, Subquery, OuterRef, IntegerField, Value
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.mixins import VaultScopedMixin
from apps.vaults.permissions import HasVaultAccess, VaultNotLocked
from .models import CustomFieldDefinition, CustomFieldValue, DocumentTemplate, Item, ItemType, ItemVersion
from .serializers import (
    CustomFieldDefinitionSerializer,
    ItemListSerializer,
    ItemSerializer,
    ItemTypeCreateSerializer,
    ItemTypeSerializer,
    ItemVersionSerializer,
    TreeNodeSerializer,
)


class ItemTypeViewSet(VaultScopedMixin, viewsets.ModelViewSet):
    permission_classes = [HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked]

    def get_queryset(self):
        return (
            ItemType.objects
            .filter(is_active=True, vault=self.current_vault)
            .prefetch_related(
                Prefetch("custom_fields", queryset=CustomFieldDefinition.objects.all())
            )
            .annotate(item_count=Count("items", filter=Q(items__is_deleted=False)))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ItemTypeCreateSerializer
        return ItemTypeSerializer

    def destroy(self, request, *args, **kwargs):
        item_type = self.get_object()
        if Item.objects.filter(item_type=item_type).exists():
            return Response(
                {"detail": "Cannot delete an item type that has existing items."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="custom-fields")
    def add_custom_field(self, request, pk=None):
        item_type = self.get_object()
        serializer = CustomFieldDefinitionSerializer(
            data=request.data,
            context={"request": request, "item_type": item_type},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(item_type=item_type)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path="custom-fields/(?P<field_id>[^/.]+)",
    )
    def manage_custom_field(self, request, pk=None, field_id=None):
        item_type = self.get_object()
        try:
            field = CustomFieldDefinition.objects.get(
                id=field_id, item_type=item_type
            )
        except CustomFieldDefinition.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            field.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = CustomFieldDefinitionSerializer(
            field, data=request.data, partial=True,
            context={"request": request, "item_type": item_type},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def _default_template(self, item_type):
        lines = [
            "{{heading}} {{title}}",
            "",
            "**Type:** {{item_type}} | **Status:** {{status}} | **Version:** {{current_version}}",
            "",
            "{{description}}",
            "",
        ]
        for cf in CustomFieldDefinition.objects.filter(item_type=item_type):
            lines.append(f"- **{cf.name}:** {{{{{cf.slug}}}}}")
        lines.append("")
        lines.append("*Created by {{created_by}} on {{created_at}} · Updated {{updated_at}}*")
        return "\n".join(lines)

    @action(detail=True, methods=["get", "put", "delete"], url_path="template")
    def template(self, request, pk=None):
        item_type = self.get_object()

        if request.method == "GET":
            try:
                dt = DocumentTemplate.objects.get(item_type=item_type)
                template_str = dt.template
                template_id = str(dt.id)
                updated_at = dt.updated_at.isoformat()
            except DocumentTemplate.DoesNotExist:
                template_str = None
                template_id = None
                updated_at = None

            builtin_fields = [
                "heading", "id", "title", "description", "status",
                "item_type", "current_version", "created_by",
                "created_at", "updated_at",
            ]
            custom_slugs = list(
                CustomFieldDefinition.objects.filter(item_type=item_type)
                .values_list("slug", flat=True)
            )

            return Response({
                "id": template_id,
                "template": template_str,
                "default_template": self._default_template(item_type),
                "available_fields": builtin_fields + custom_slugs,
                "updated_at": updated_at,
            })

        if request.method == "PUT":
            template_str = request.data.get("template", "")
            dt, _created = DocumentTemplate.all_objects.get_or_create(
                item_type=item_type,
                is_deleted=False,
                defaults={"template": template_str, "updated_by": request.user},
            )
            if not _created:
                dt.template = template_str
                dt.updated_by = request.user
                dt.save(update_fields=["template", "updated_by", "updated_at"])
            return Response({
                "id": str(dt.id),
                "template": dt.template,
                "updated_at": dt.updated_at.isoformat(),
            })

        # DELETE
        try:
            dt = DocumentTemplate.objects.get(item_type=item_type)
            dt.delete()
        except DocumentTemplate.DoesNotExist:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemViewSet(VaultScopedMixin, viewsets.ModelViewSet):
    permission_classes = [HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked]
    filterset_fields = ["item_type__slug", "status", "created_by"]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "created_at", "updated_at", "status"]

    def get_queryset(self):
        return Item.objects.select_related("item_type", "created_by").filter(
            item_type__vault=self.current_vault
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ItemListSerializer
        if self.action in ("roots", "children"):
            return TreeNodeSerializer
        return ItemSerializer

    def _composition_types(self):
        return RelationType.objects.filter(
            kind=RelationType.Kind.COMPOSITION, vault=self.current_vault
        )

    def _annotate_suspect_links(self, qs):
        """Annotate items with whether they have any suspect trace relations.

        A relation is suspect if either stored version is behind the item's
        current_version — covers both "this item changed" and "other item changed".
        """
        non_comp = ~Q(relation_type__kind=RelationType.Kind.COMPOSITION)
        not_pinned = Q(version_pinned=False)
        suspect_as_source = ItemRelation.objects.filter(
            non_comp,
            not_pinned,
            source_id=OuterRef("pk"),
        ).filter(
            Q(source_version__lt=OuterRef("current_version"))
            | Q(target_version__lt=F("target__current_version"))
        )
        suspect_as_target = ItemRelation.objects.filter(
            non_comp,
            not_pinned,
            target_id=OuterRef("pk"),
        ).filter(
            Q(target_version__lt=OuterRef("current_version"))
            | Q(source_version__lt=F("source__current_version"))
        )
        return qs.annotate(
            has_suspect_links=Exists(suspect_as_source) | Exists(suspect_as_target)
        )

    def _annotate_suspect_descendants(self, qs):
        """Annotate whether any descendant (via composition) has suspect trace links.

        Uses a recursive CTE to walk the composition tree downward and check
        if any descendant item participates in a suspect trace relation.
        """
        sql = """
        EXISTS (
            WITH RECURSIVE desc_tree AS (
                SELECT ir.target_id AS id
                FROM relations_item_relation ir
                JOIN relations_relation_type rt ON ir.relation_type_id = rt.id
                WHERE ir.source_id = "items_item"."id"
                  AND rt.kind = 'composition'
                  AND ir.is_deleted = false
                  AND rt.is_deleted = false
                UNION ALL
                SELECT ir.target_id
                FROM relations_item_relation ir
                JOIN relations_relation_type rt ON ir.relation_type_id = rt.id
                JOIN desc_tree d ON ir.source_id = d.id
                WHERE rt.kind = 'composition'
                  AND ir.is_deleted = false
                  AND rt.is_deleted = false
            )
            SELECT 1 FROM desc_tree d
            WHERE EXISTS (
                SELECT 1 FROM relations_item_relation r
                JOIN relations_relation_type rt ON r.relation_type_id = rt.id
                WHERE rt.kind != 'composition'
                  AND r.is_deleted = false
                  AND rt.is_deleted = false
                  AND r.version_pinned = false
                AND (
                    (r.source_id = d.id AND (
                        r.source_version < (SELECT current_version FROM items_item WHERE id = d.id AND is_deleted = false)
                        OR r.target_version < (SELECT current_version FROM items_item WHERE id = r.target_id AND is_deleted = false)
                    ))
                    OR
                    (r.target_id = d.id AND (
                        r.target_version < (SELECT current_version FROM items_item WHERE id = d.id AND is_deleted = false)
                        OR r.source_version < (SELECT current_version FROM items_item WHERE id = r.source_id AND is_deleted = false)
                    ))
                )
            )
        )
        """
        return qs.annotate(
            has_suspect_descendants=RawSQL(sql, [], output_field=BooleanField())
        )

    def _annotate_child_count(self, qs, composition_types):
        child_count_sq = Subquery(
            ItemRelation.objects.filter(
                relation_type__in=composition_types,
                source=OuterRef("pk"),
            )
            .values("source")
            .annotate(cnt=Count("id"))
            .values("cnt"),
            output_field=IntegerField(),
        )
        return qs.annotate(child_count=Coalesce(child_count_sq, Value(0)))

    @action(detail=False, methods=["get"])
    def roots(self, request):
        comp_types = self._composition_types()
        if not comp_types.exists():
            qs = Item.objects.none()
        else:
            child_ids = ItemRelation.objects.filter(
                relation_type__in=comp_types,
            ).values_list("target_id", flat=True)
            qs = self.get_queryset().exclude(id__in=child_ids)
            qs = self._annotate_child_count(qs, comp_types)
            qs = self._annotate_suspect_links(qs)
            qs = self._annotate_suspect_descendants(qs)
        qs = qs.order_by("title")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        comp_types = self._composition_types()
        if not comp_types.exists():
            qs = Item.objects.none()
        else:
            child_ids = ItemRelation.objects.filter(
                relation_type__in=comp_types,
                source_id=pk,
            ).values_list("target_id", flat=True)
            qs = self.get_queryset().filter(id__in=child_ids)
            qs = self._annotate_child_count(qs, comp_types)
            qs = self._annotate_suspect_links(qs)
            qs = self._annotate_suspect_descendants(qs)
            # Annotate with position from the composition relation
            pos_sq = Subquery(
                ItemRelation.objects.filter(
                    relation_type__in=comp_types,
                    source_id=pk,
                    target_id=OuterRef("pk"),
                ).values("position")[:1],
                output_field=IntegerField(),
            )
            qs = qs.annotate(rel_position=Coalesce(pos_sq, Value(0)))
        qs = qs.order_by("rel_position", "title")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="reorder-children")
    def reorder_children(self, request, pk=None):
        child_ids = request.data.get("child_ids", [])
        if not child_ids:
            return Response(
                {"detail": "child_ids is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comp_types = self._composition_types()
        rels = ItemRelation.objects.filter(
            relation_type__in=comp_types,
            source_id=pk,
            target_id__in=child_ids,
        )
        rel_map = {str(r.target_id): r for r in rels}
        to_update = []
        for i, cid in enumerate(child_ids):
            rel = rel_map.get(cid)
            if rel:
                rel.position = i * 10
                to_update.append(rel)
        if to_update:
            ItemRelation.objects.bulk_update(to_update, ["position"])
        return Response({"status": "ok"})

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        item = self.get_object()
        qs = ItemVersion.objects.filter(item=item).select_related("created_by")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ItemVersionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ItemVersionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path=r"versions/(?P<version_number>\d+)")
    def version_detail(self, request, pk=None, version_number=None):
        """Return data for a specific version of an item."""
        item = self.get_object()
        version_number = int(version_number)

        if version_number < 1 or version_number > item.current_version:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if version_number == item.current_version:
            # Synthesize from live item state
            cfv_qs = CustomFieldValue.objects.filter(item=item).select_related("field_definition")
            return Response({
                "version_number": item.current_version,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "custom_fields_snapshot": {
                    cfv.field_definition.slug: cfv.value for cfv in cfv_qs
                },
                "created_by": item.created_by_id,
                "created_by_username": item.created_by.username,
                "created_at": item.updated_at,
                "change_summary": "",
            })

        version = ItemVersion.objects.filter(
            item=item, version_number=version_number
        ).select_related("created_by").first()
        if not version:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ItemVersionSerializer(version)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="editor-data")
    def editor_data(self, request, pk=None):
        """Return structured data for each item in the composition tree rooted here.

        Used by the document editor mode to render editable templates for the
        current item and all its composition children.
        """
        item = self.get_object()
        composition_types = self._composition_types()

        templates = {
            dt.item_type_id: dt.template
            for dt in DocumentTemplate.objects.all()
        }

        seen = set()
        result_items = []

        def _default_tmpl(cf_defs):
            lines = [
                "{{heading}} {{title}}",
                "",
                "**Type:** {{item_type}} | **Status:** {{status}} | **Version:** {{current_version}}",
                "",
                "{{description}}",
                "",
            ]
            for cf in cf_defs:
                lines.append(f"- **{cf['name']}:** {{{{{cf['slug']}}}}}")
            lines.append("")
            lines.append("*Created by {{created_by}} on {{created_at}} · Updated {{updated_at}}*")
            return "\n".join(lines)

        def _collect(current_id, depth):
            if current_id in seen or depth > 6:
                return
            seen.add(current_id)

            try:
                current_item = (
                    Item.objects.select_related("item_type", "created_by")
                    .get(pk=current_id)
                )
            except Item.DoesNotExist:
                return

            field_values = (
                CustomFieldValue.objects.filter(item=current_item)
                .select_related("field_definition")
                .order_by("field_definition__display_order")
            )
            custom_fields = {fv.field_definition.slug: fv.value for fv in field_values}

            cf_defs = list(
                CustomFieldDefinition.objects.filter(item_type=current_item.item_type)
                .order_by("display_order")
                .values("slug", "name", "field_kind", "options")
            )

            result_items.append({
                "id": str(current_item.id),
                "depth": depth,
                "title": current_item.title,
                "description": current_item.description or "",
                "status": current_item.status,
                "item_type_id": str(current_item.item_type_id),
                "item_type_name": current_item.item_type.name,
                "current_version": current_item.current_version,
                "created_by": current_item.created_by.username,
                "created_at": current_item.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": current_item.updated_at.strftime("%Y-%m-%d %H:%M"),
                "custom_fields": custom_fields,
                "custom_field_definitions": cf_defs,
                "template": templates.get(current_item.item_type_id),
                "default_template": _default_tmpl(cf_defs),
            })

            child_relations = (
                ItemRelation.objects.filter(
                    relation_type__in=composition_types,
                    source=current_item,
                )
                .order_by("position", "created_at")
                .values_list("target_id", flat=True)
            )
            for child_id in child_relations:
                _collect(child_id, depth + 1)

        _collect(str(item.id), 1)
        return Response({"items": result_items})

    @action(
        detail=True, methods=["get"],
        url_path=r"table-field/(?P<field_slug>[^/.]+)/data",
        url_name="table-field-data",
    )
    def table_field_data(self, request, pk=None, field_slug=None):
        """
        Return traversal data for an item-embedded table field.

        The owning item is the implicit seed; the column schema comes from
        CustomFieldDefinition.options["columns"].
        """
        from apps.items.models import CustomFieldValue, ItemTableAnnotation
        from apps.matrices.traversal import compute_row_hash, evaluate_formulas, run_traversal

        item = self.get_object()
        try:
            field_def = CustomFieldDefinition.objects.get(
                item_type=item.item_type,
                slug=field_slug,
                field_kind=CustomFieldDefinition.FieldKind.TABLE,
            )
        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"detail": f"No table field with slug '{field_slug}' on this item type."},
                status=status.HTTP_404_NOT_FOUND,
            )

        raw_column_specs = field_def.options.get("columns", [])
        # Ensure each spec has a name for the traversal engine
        column_specs = []
        for i, spec in enumerate(raw_column_specs):
            s = dict(spec)
            if "name" not in s:
                s["name"] = s.get("slug") or f"col{i}"
            column_specs.append(s)

        rows, formula_col_indices, non_traversal_col_indices = run_traversal(
            column_specs, [item]
        )

        # Drop rows where the first traversal column has no match.
        # (For item-embedded tables the owning item is always the implicit seed at row[0];
        # if row[1] is None there are no linked items — no row to show.)
        rows = [row for row in rows if len(row) > 1 and row[1] is not None]

        # Evaluate formula columns (item is implicit seed at row[0])
        if formula_col_indices:
            # Use a dummy seed spec with a reserved name (not referenceable)
            dummy_seed = {"name": "_seed", "kind": "seed"}
            all_specs_with_seed = [dummy_seed] + column_specs
            evaluate_formulas(all_specs_with_seed, rows, formula_col_indices, non_traversal_col_indices)

        # Compute row hashes and load annotations
        annotation_col_slugs = [
            spec.get("slug") or spec["name"]
            for spec in column_specs
            if spec.get("kind") == "annotation"
        ]
        annotation_lookup: dict[tuple, str] = {}
        row_hashes = []
        if rows:
            row_hashes = [compute_row_hash(row, non_traversal_col_indices) for row in rows]
            if annotation_col_slugs:
                anns = ItemTableAnnotation.objects.filter(
                    item=item,
                    field_definition=field_def,
                    column_slug__in=annotation_col_slugs,
                    row_hash__in=row_hashes,
                )
                for ann in anns:
                    annotation_lookup[(ann.column_slug, ann.row_hash)] = ann.value

        # Build name-to-row-idx map (col0 at row[1], col1 at row[2], etc.)
        name_to_row_idx = {spec["name"]: i + 1 for i, spec in enumerate(column_specs)}

        # Resolve item_field columns
        item_field_lookup: dict[tuple, object] = {}
        item_field_specs = [spec for spec in column_specs if spec.get("kind") == "item_field"]
        if item_field_specs and rows:
            for spec in item_field_specs:
                source_ref = spec.get("source_ref", "")
                field_slug_val = spec.get("field_slug")
                if not source_ref or not field_slug_val:
                    continue
                row_src_idx = name_to_row_idx.get(source_ref)
                if row_src_idx is None:
                    continue
                item_ids = {
                    row[row_src_idx].id
                    for row in rows
                    if row_src_idx < len(row) and row[row_src_idx] is not None
                }
                if not item_ids:
                    continue
                cfvs = CustomFieldValue.objects.filter(
                    item_id__in=item_ids,
                    field_definition__slug=field_slug_val,
                ).select_related("field_definition")
                for cfv in cfvs:
                    item_field_lookup[(str(cfv.item_id), field_slug_val)] = cfv.value

        def serialize_cell(cell, col_idx, row, row_hash):
            # col_idx 0 = implicit seed (not in column_specs); col_idx 1+ = column_specs[col_idx-1]
            if col_idx == 0:
                return None  # implicit seed row is not serialized
            spec = column_specs[col_idx - 1]
            kind = spec.get("kind", "traversal")

            if kind == "formula":
                return {"value": cell} if cell is not None else None

            if kind == "annotation":
                col_slug = spec.get("slug", "")
                value = annotation_lookup.get((col_slug, row_hash), "")
                return {
                    "annotation": True,
                    "value": value,
                    "row_hash": row_hash,
                    "column_slug": col_slug,
                }

            if kind == "item_field":
                source_ref = spec.get("source_ref", "")
                field_slug_val = spec.get("field_slug", "")
                row_src_idx = name_to_row_idx.get(source_ref)
                source_item = row[row_src_idx] if row_src_idx is not None and row_src_idx < len(row) else None
                if source_item is not None and hasattr(source_item, "id"):
                    value = item_field_lookup.get((str(source_item.id), field_slug_val))
                    return {"item_field": True, "value": value}
                return {"item_field": True, "value": None}

            # traversal
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
            # Skip col 0 (implicit seed) in output — start from col 1
            serialized_rows.append([
                serialize_cell(cell, col_idx, row, row_hash)
                for col_idx, cell in enumerate(row)
                if col_idx > 0
            ])

        return Response({
            "columns": [
                {
                    "position": i,
                    "heading": spec.get("label", ""),
                    "source": spec["name"],
                    "kind": spec.get("kind"),
                    "slug": spec.get("slug") or spec.get("field_slug") or None,
                }
                for i, spec in enumerate(column_specs)
            ],
            "rows": serialized_rows,
        })

    @action(
        detail=True, methods=["patch"],
        url_path=r"table-field/(?P<field_slug>[^/.]+)/annotate",
        url_name="table-field-annotate",
    )
    def table_field_annotate(self, request, pk=None, field_slug=None):
        """Upsert an annotation value for a specific annotation column and row in a table field."""
        from rest_framework import serializers as drf_serializers
        from apps.items.models import ItemTableAnnotation

        item = self.get_object()
        try:
            field_def = CustomFieldDefinition.objects.get(
                item_type=item.item_type,
                slug=field_slug,
                field_kind=CustomFieldDefinition.FieldKind.TABLE,
            )
        except CustomFieldDefinition.DoesNotExist:
            return Response(
                {"detail": f"No table field with slug '{field_slug}' on this item type."},
                status=status.HTTP_404_NOT_FOUND,
            )

        column_slug = request.data.get("column_slug", "").strip()
        row_hash = request.data.get("row_hash", "").strip()
        value = request.data.get("value", "")

        if not column_slug:
            return Response({"column_slug": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if not row_hash:
            return Response({"row_hash": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the column_slug exists as an annotation column in this field's schema
        columns = field_def.options.get("columns", [])
        valid_slugs = {
            col["slug"] for col in columns
            if col.get("kind") == "annotation" and col.get("slug")
        }
        if column_slug not in valid_slugs:
            return Response(
                {"column_slug": [f"No annotation column with slug '{column_slug}' in this table field."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        annotation, _ = ItemTableAnnotation.objects.update_or_create(
            item=item,
            field_definition=field_def,
            column_slug=column_slug,
            row_hash=row_hash,
            defaults={"value": value, "updated_by": request.user},
        )

        return Response({
            "column_slug": annotation.column_slug,
            "row_hash": annotation.row_hash,
            "value": annotation.value,
        })

    @action(detail=True, methods=["get"])
    def ancestors(self, request, pk=None):
        import uuid as _uuid
        try:
            _uuid.UUID(pk)
        except (ValueError, AttributeError):
            return Response([])
        comp_types = self._composition_types()
        if not comp_types.exists():
            return Response([])
        ancestors = []
        current_id = pk
        seen = set()
        while current_id and current_id not in seen:
            seen.add(current_id)
            parent_rel = ItemRelation.objects.filter(
                relation_type__in=comp_types,
                target_id=current_id,
            ).values_list("source_id", flat=True).first()
            if parent_rel:
                ancestors.append(str(parent_rel))
                current_id = parent_rel
            else:
                break
        ancestors.reverse()
        return Response(ancestors)
