import re

from apps.items.models import CustomFieldValue, DocumentTemplate, Item
from apps.relations.models import RelationType, ItemRelation


def generate_markdown(item_id, max_depth=6):
    """Recursively walk the composition tree and produce a markdown document."""
    seen = set()
    composition_types = RelationType.objects.filter(kind=RelationType.Kind.COMPOSITION)

    # Cache custom templates keyed by item_type_id
    templates = {
        dt.item_type_id: dt.template
        for dt in DocumentTemplate.objects.all()
    }

    lines = []

    def _build_context(item, depth):
        """Build a dict of all available placeholder values for an item."""
        ctx = {
            "heading": "#" * min(depth, 6),
            "id": str(item.id),
            "title": item.title,
            "description": item.description or "",
            "status": item.status.replace("_", " "),
            "item_type": item.item_type.name,
            "current_version": str(item.current_version),
            "created_by": item.created_by.username,
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
        field_values = (
            CustomFieldValue.objects.filter(item=item)
            .select_related("field_definition")
            .order_by("field_definition__display_order")
        )
        for fv in field_values:
            ctx[fv.field_definition.slug] = str(fv.value)
        return ctx, field_values

    def _render_with_template(template_str, ctx):
        """Replace {{field}} placeholders with values from ctx."""
        def replacer(match):
            key = match.group(1)
            return ctx.get(key, "")
        return re.sub(r"\{\{([\w-]+)\}\}", replacer, template_str)

    def _render_default(item, ctx, field_values):
        """Original hardcoded rendering logic."""
        heading = ctx["heading"]
        lines.append(f"{heading} {item.title}")
        lines.append("")

        meta_parts = [
            f"**Type:** {item.item_type.name}",
            f"**Status:** {ctx['status']}",
            f"**Version:** {item.current_version}",
        ]
        lines.append(" | ".join(meta_parts))
        lines.append("")

        if item.description:
            lines.append(item.description)
            lines.append("")

        if field_values.exists():
            for fv in field_values:
                lines.append(f"- **{fv.field_definition.name}:** {fv.value}")
            lines.append("")

        lines.append(
            f"*Created by {item.created_by.username} on "
            f"{item.created_at.strftime('%Y-%m-%d %H:%M')} · "
            f"Updated {item.updated_at.strftime('%Y-%m-%d %H:%M')}*"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

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

        ctx, field_values = _build_context(item, depth)
        custom_template = templates.get(item.item_type_id)

        if custom_template:
            rendered = _render_with_template(custom_template, ctx)
            lines.append(rendered)
            lines.append("")
            lines.append("---")
            lines.append("")
        else:
            _render_default(item, ctx, field_values)

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
