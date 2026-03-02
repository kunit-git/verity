from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReadOnlyOrEditor
from apps.items.models import Item
from apps.relations.models import ItemRelation, RelationType
from .models import Matrix, MatrixColumn
from .serializers import MatrixSerializer, MatrixWriteSerializer


class MatrixViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrEditor]

    def get_queryset(self):
        return Matrix.objects.select_related("created_by").prefetch_related(
            "columns__seed_item_type",
            "columns__seed_container",
            "columns__relation_type",
        ).all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MatrixWriteSerializer
        return MatrixSerializer

    @action(detail=True, methods=["get"], url_path="data")
    def data(self, request, pk=None):
        matrix = self.get_object()
        columns = list(
            matrix.columns.select_related(
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

        # Traverse subsequent columns, expanding rows
        for col in columns[1:]:
            if not col.relation_type or not col.direction:
                rows = [row + [None] for row in rows]
                continue

            new_rows = []
            for row in rows:
                last_item = row[-1]
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

        def serialize_cell(item):
            if item is None:
                return None
            return {
                "id": str(item.id),
                "title": item.title,
                "item_type_name": item.item_type.name,
                "item_type_slug": item.item_type.slug,
            }

        return Response({
            "columns": [
                {"position": col.position, "label": col.label}
                for col in columns
            ],
            "rows": [
                [serialize_cell(cell) for cell in row]
                for row in rows
            ],
        })
