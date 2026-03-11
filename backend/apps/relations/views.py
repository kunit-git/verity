from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.items.models import Item, ItemVersion
from .models import ItemRelation, RelationType
from .serializers import ItemRelationSerializer, RelationTypeSerializer


class RelationTypeViewSet(viewsets.ModelViewSet):
    queryset = RelationType.objects.filter(is_active=True).select_related(
        "source_item_type", "target_item_type"
    )
    serializer_class = RelationTypeSerializer
    permission_classes = [ReadOnlyOrEditor]

    def destroy(self, request, *args, **kwargs):
        relation_type = self.get_object()
        if relation_type.is_builtin:
            return Response(
                {"detail": "Built-in relation types cannot be deleted."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class ItemRelationViewSet(viewsets.ModelViewSet):
    serializer_class = ItemRelationSerializer
    permission_classes = [ReadOnlyOrEditor]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["relation_type", "source", "target"]

    def get_queryset(self):
        return ItemRelation.objects.select_related(
            "relation_type",
            "source",
            "source__item_type",
            "target",
            "target__item_type",
        ).all()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirm a relation, optionally pinning to specific versions.

        Body (all optional):
            source_version: int  — defaults to current
            target_version: int  — defaults to current
            version_pinned: bool — defaults to false
        """
        relation = self.get_object()
        source_ver = request.data.get("source_version", relation.source.current_version)
        target_ver = request.data.get("target_version", relation.target.current_version)
        pinned = request.data.get("version_pinned", False)

        # Validate versions exist
        from apps.items.models import ItemVersion
        if source_ver != relation.source.current_version:
            if not ItemVersion.objects.filter(item=relation.source, version_number=source_ver).exists():
                return Response(
                    {"source_version": f"Version {source_ver} does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if target_ver != relation.target.current_version:
            if not ItemVersion.objects.filter(item=relation.target, version_number=target_ver).exists():
                return Response(
                    {"target_version": f"Version {target_ver} does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        relation.source_version = source_ver
        relation.target_version = target_ver
        relation.version_pinned = pinned
        relation.save(update_fields=["source_version", "target_version", "version_pinned"])
        serializer = self.get_serializer(relation)
        return Response(serializer.data)


class ItemNavigationView(viewsets.ViewSet):
    """Returns navigation context for the spatial navigator."""

    permission_classes = [ReadOnlyOrEditor]

    @staticmethod
    def _resolve_ref(item, pinned_version=None, self_version=None, self_current_version=None, version_pinned=False):
        """Build a navigation ref, resolving title from a pinned version if set.

        A relation is suspect if:
        - The other item changed: pinned_version < item.current_version
        - The current item changed: self_version < self_current_version
        - AND the relation is not explicitly pinned by the user
        """
        other_suspect = pinned_version is not None and pinned_version < item.current_version
        self_suspect = (
            self_version is not None
            and self_current_version is not None
            and self_version < self_current_version
        )
        is_suspect = (other_suspect or self_suspect) and not version_pinned
        ref = {
            "id": str(item.id),
            "title": item.title,
            "item_type_slug": item.item_type.slug,
            "pinned_version": pinned_version,
            "current_version": item.current_version,
            "self_pinned_version": self_version,
            "self_current_version": self_current_version,
            "is_suspect": is_suspect,
            "other_changed": other_suspect,
            "self_changed": self_suspect,
            "is_version_pinned": version_pinned,
        }
        if pinned_version is not None:
            version = ItemVersion.objects.filter(
                item=item, version_number=pinned_version
            ).first()
            if version:
                ref["title"] = version.title
        return ref

    def retrieve(self, request, pk=None):
        try:
            item = Item.objects.get(pk=pk)
        except Item.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Find all composition-kind relation types
        comp_types = RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)

        parent = None
        children = []
        siblings = []

        if comp_types.exists():
            # Parent: item where current item is a target of a composition relation
            parent_rel = ItemRelation.objects.filter(
                relation_type__in=comp_types, target=item
            ).select_related("source", "source__item_type").first()

            if parent_rel:
                parent = self._resolve_ref(parent_rel.source)
                # Siblings: other targets of the same parent via composition
                sibling_rels = (
                    ItemRelation.objects.filter(
                        relation_type__in=comp_types, source=parent_rel.source
                    )
                    .exclude(target=item)
                    .select_related("target", "target__item_type")
                    .order_by("position")
                )
                siblings = [
                    self._resolve_ref(r.target)
                    for r in sibling_rels
                ]

            # Children: targets where current is source of a composition relation
            child_rels = ItemRelation.objects.filter(
                relation_type__in=comp_types, source=item
            ).select_related("target", "target__item_type").order_by("position")
            children = [
                self._resolve_ref(r.target)
                for r in child_rels
            ]

        # Left: incoming non-composition relations (current is target)
        incoming = (
            ItemRelation.objects.filter(target=item)
            .exclude(relation_type__in=comp_types)
            .select_related("source", "source__item_type", "relation_type")
        )
        left = [
            {
                **self._resolve_ref(
                    r.source, r.source_version,
                    self_version=r.target_version,
                    self_current_version=item.current_version,
                    version_pinned=r.version_pinned,
                ),
                "relation_id": str(r.id),
                "relation_type": r.relation_type.name,
                "relation_label": r.relation_type.reverse_label,
            }
            for r in incoming
        ]

        # Right: outgoing non-composition relations (current is source)
        outgoing = (
            ItemRelation.objects.filter(source=item)
            .exclude(relation_type__in=comp_types)
            .select_related("target", "target__item_type", "relation_type")
        )
        right = [
            {
                **self._resolve_ref(
                    r.target, r.target_version,
                    self_version=r.source_version,
                    self_current_version=item.current_version,
                    version_pinned=r.version_pinned,
                ),
                "relation_id": str(r.id),
                "relation_type": r.relation_type.name,
                "relation_label": r.relation_type.forward_label,
            }
            for r in outgoing
        ]

        return Response(
            {
                "parent": parent,
                "children": children,
                "siblings": siblings,
                "left": left,
                "right": right,
            }
        )
