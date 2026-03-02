from apps.items.models import Item, CustomFieldValue
from apps.relations.models import RelationType, ItemRelation


def generate_markdown(item_id, max_depth=6):
    """Recursively walk the composition tree and produce a markdown document."""
    seen = set()
    composition_types = RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)
    lines = []

    def _render(current_id, depth):
        if current_id in seen or depth > max_depth:
            return
        seen.add(current_id)

        try:
            item = (
                Item.objects.select_related("item_type", "created_by")
                .get(pk=current_id)
            )
        except Item.DoesNotExist:
            return

        heading = "#" * min(depth, 6)
        lines.append(f"{heading} {item.title}")
        lines.append("")

        # Metadata line
        meta_parts = [
            f"**Type:** {item.item_type.name}",
            f"**Status:** {item.status.replace('_', ' ')}",
            f"**Version:** {item.current_version}",
        ]
        lines.append(" | ".join(meta_parts))
        lines.append("")

        # Description
        if item.description:
            lines.append(item.description)
            lines.append("")

        # Custom fields
        field_values = (
            CustomFieldValue.objects.filter(item=item)
            .select_related("field_definition")
            .order_by("field_definition__display_order")
        )
        if field_values.exists():
            for fv in field_values:
                lines.append(f"- **{fv.field_definition.name}:** {fv.value}")
            lines.append("")

        # Created by / dates
        lines.append(
            f"*Created by {item.created_by.username} on "
            f"{item.created_at.strftime('%Y-%m-%d %H:%M')} · "
            f"Updated {item.updated_at.strftime('%Y-%m-%d %H:%M')}*"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Recurse into composition children
        child_relations = (
            ItemRelation.objects.filter(
                relation_type__in=composition_types,
                source=item,
            )
            .order_by("position", "created_at")
            .values_list("target_id", flat=True)
        )
        for child_id in child_relations:
            _render(child_id, depth + 1)

    _render(item_id, 1)
    return "\n".join(lines)
