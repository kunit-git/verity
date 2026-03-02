from django.db.models import BooleanField, Count, Exists, F, Q, Subquery, OuterRef, IntegerField, Value
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.relations.models import ItemRelation, RelationType
from .models import CustomFieldDefinition, Item, ItemType, ItemVersion
from .serializers import (
    CustomFieldDefinitionSerializer,
    ItemListSerializer,
    ItemSerializer,
    ItemTypeCreateSerializer,
    ItemTypeSerializer,
    ItemVersionSerializer,
    TreeNodeSerializer,
)


class ItemTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrEditor]

    def get_queryset(self):
        return (
            ItemType.objects
            .filter(is_active=True)
            .prefetch_related("custom_fields")
            .annotate(item_count=Count("items"))
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ItemTypeCreateSerializer
        return ItemTypeSerializer

    def destroy(self, request, *args, **kwargs):
        item_type = self.get_object()
        if item_type.items.exists():
            return Response(
                {"detail": "Cannot delete an item type that has existing items."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="custom-fields")
    def add_custom_field(self, request, pk=None):
        item_type = self.get_object()
        serializer = CustomFieldDefinitionSerializer(data=request.data)
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
            field, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ItemViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrEditor]
    filterset_fields = ["item_type__slug", "status", "created_by"]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "created_at", "updated_at", "status"]

    def get_queryset(self):
        return Item.objects.select_related("item_type", "created_by").all()

    def get_serializer_class(self):
        if self.action == "list":
            return ItemListSerializer
        if self.action in ("roots", "children"):
            return TreeNodeSerializer
        return ItemSerializer

    def _composition_types(self):
        return RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)

    def _annotate_suspect_links(self, qs):
        """Annotate items with whether they have any suspect trace relations.

        A relation is suspect if either stored version is behind the item's
        current_version — covers both "this item changed" and "other item changed".
        """
        non_comp = ~Q(relation_type__kind=RelationType.Kind.COMPOSITION)
        suspect_as_source = ItemRelation.objects.filter(
            non_comp,
            source_id=OuterRef("pk"),
        ).filter(
            Q(source_version__lt=OuterRef("current_version"))
            | Q(target_version__lt=F("target__current_version"))
        )
        suspect_as_target = ItemRelation.objects.filter(
            non_comp,
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
                WHERE ir.source_id = "items_item"."id" AND rt.kind = 'composition'
                UNION ALL
                SELECT ir.target_id
                FROM relations_item_relation ir
                JOIN relations_relation_type rt ON ir.relation_type_id = rt.id
                JOIN desc_tree d ON ir.source_id = d.id
                WHERE rt.kind = 'composition'
            )
            SELECT 1 FROM desc_tree d
            WHERE EXISTS (
                SELECT 1 FROM relations_item_relation r
                JOIN relations_relation_type rt ON r.relation_type_id = rt.id
                WHERE rt.kind != 'composition'
                AND (
                    (r.source_id = d.id AND (
                        r.source_version < (SELECT current_version FROM items_item WHERE id = d.id)
                        OR r.target_version < (SELECT current_version FROM items_item WHERE id = r.target_id)
                    ))
                    OR
                    (r.target_id = d.id AND (
                        r.target_version < (SELECT current_version FROM items_item WHERE id = d.id)
                        OR r.source_version < (SELECT current_version FROM items_item WHERE id = r.source_id)
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
            qs = Item.objects.exclude(id__in=child_ids).select_related("item_type")
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
            qs = Item.objects.filter(id__in=child_ids).select_related("item_type")
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
        qs = item.versions.select_related("created_by").all()
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ItemVersionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ItemVersionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def ancestors(self, request, pk=None):
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
