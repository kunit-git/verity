import re

from apps.items.models import CustomFieldDefinition, CustomFieldValue, DocumentTemplate, Item
from apps.relations.models import RelationType, ItemRelation


def _render_table_field_markdown(item, field_def):
    """Render an item-embedded table field as a Markdown table string."""
    from apps.items.models import ItemTableAnnotation
    from apps.matrices.traversal import compute_row_hash, evaluate_formulas, run_traversal

    raw_column_specs = field_def.options.get("columns", [])
    if not raw_column_specs:
        return ""

    # Ensure each spec has a name for the traversal engine
    column_specs = []
    for i, spec in enumerate(raw_column_specs):
        s = dict(spec)
        if "name" not in s:
            s["name"] = s.get("slug") or f"col{i}"
        column_specs.append(s)

    # Build name-to-row-idx map (col0 at row[1], col1 at row[2], etc.)
    name_to_row_idx = {spec["name"]: i + 1 for i, spec in enumerate(column_specs)}

    rows, formula_col_indices, non_traversal_col_indices = run_traversal(column_specs, [item])
    rows = [row for row in rows if len(row) > 1 and row[1] is not None]
    if not rows:
        return ""

    if formula_col_indices:
        dummy_seed = {"name": "_seed", "kind": "seed"}
        all_specs_with_seed = [dummy_seed] + column_specs
        evaluate_formulas(all_specs_with_seed, rows, formula_col_indices, non_traversal_col_indices)

    row_hashes = [compute_row_hash(row, non_traversal_col_indices) for row in rows]

    annotation_col_slugs = [
        spec.get("slug") or spec["name"]
        for spec in column_specs
        if spec.get("kind") == "annotation"
    ]
    annotation_lookup: dict[tuple, str] = {}
    if annotation_col_slugs:
        for ann in ItemTableAnnotation.objects.filter(
            item=item,
            field_definition=field_def,
            column_slug__in=annotation_col_slugs,
            row_hash__in=row_hashes,
        ):
            annotation_lookup[(ann.column_slug, ann.row_hash)] = ann.value

    item_field_lookup: dict[tuple, object] = {}
    for spec in column_specs:
        if spec.get("kind") != "item_field":
            continue
        source_ref = spec.get("source_ref", "")
        field_slug_val = spec.get("field_slug", "")
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
        for cfv in CustomFieldValue.objects.filter(
            item_id__in=item_ids, field_definition__slug=field_slug_val
        ):
            item_field_lookup[(str(cfv.item_id), field_slug_val)] = cfv.value

    def _cell_text(col_idx, cell, row, row_hash):
        """Return a plain-text representation of a cell for Markdown."""
        spec = column_specs[col_idx - 1]  # col_idx 1 = spec[0]
        kind = spec.get("kind", "traversal")

        if kind == "formula":
            if cell is None:
                return "—"
            return str(int(cell)) if isinstance(cell, float) and cell == int(cell) else f"{cell:.2f}"

        if kind == "annotation":
            col_slug = spec.get("slug", "")
            return annotation_lookup.get((col_slug, row_hash), "")

        if kind == "item_field":
            source_ref = spec.get("source_ref", "")
            field_slug_val = spec.get("field_slug", "")
            row_src_idx = name_to_row_idx.get(source_ref)
            source_item = row[row_src_idx] if row_src_idx is not None and row_src_idx < len(row) else None
            if source_item is not None and hasattr(source_item, "id"):
                val = item_field_lookup.get((str(source_item.id), field_slug_val))
                return str(val) if val is not None else "—"
            return "—"

        # traversal
        if cell is None:
            return "—"
        return cell.title

    headers = [spec.get("label", f"Col {i+1}") for i, spec in enumerate(column_specs)]
    md_lines = []
    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join("---" for _ in headers) + " |")

    for row_idx, row in enumerate(rows):
        rh = row_hashes[row_idx]
        cells = [
            _cell_text(col_idx, cell, row, rh)
            for col_idx, cell in enumerate(row)
            if col_idx > 0
        ]
        md_lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")

    return "\n".join(md_lines)


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
            if fv.field_definition.field_kind == CustomFieldDefinition.FieldKind.MERMAID:
                ctx[fv.field_definition.slug] = f"\n```mermaid\n{fv.value}\n```\n"
            else:
                ctx[fv.field_definition.slug] = str(fv.value)

        # Render table fields as Markdown tables
        table_field_defs = CustomFieldDefinition.objects.filter(
            item_type=item.item_type,
            field_kind=CustomFieldDefinition.FieldKind.TABLE,
        ).order_by("display_order")
        for field_def in table_field_defs:
            ctx[field_def.slug] = _render_table_field_markdown(item, field_def)

        return ctx, field_values, table_field_defs

    def _render_with_template(template_str, ctx):
        """Replace {{field}} placeholders with values from ctx."""
        def replacer(match):
            key = match.group(1)
            return ctx.get(key, "")
        return re.sub(r"\{\{([\w-]+)\}\}", replacer, template_str)

    def _render_default(item, ctx, field_values, table_field_defs):
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
                if fv.field_definition.field_kind == CustomFieldDefinition.FieldKind.MERMAID:
                    lines.append(f"**{fv.field_definition.name}:**")
                    lines.append("")
                    lines.append(f"```mermaid\n{fv.value}\n```")
                else:
                    lines.append(f"- **{fv.field_definition.name}:** {fv.value}")
            lines.append("")

        for field_def in table_field_defs:
            table_md = ctx.get(field_def.slug, "")
            if table_md:
                lines.append(f"**{field_def.name}:**")
                lines.append("")
                lines.append(table_md)
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

        ctx, field_values, table_field_defs = _build_context(item, depth)
        custom_template = templates.get(item.item_type_id)

        if custom_template:
            rendered = _render_with_template(custom_template, ctx)
            lines.append(rendered)
            lines.append("")
            lines.append("---")
            lines.append("")
        else:
            _render_default(item, ctx, field_values, table_field_defs)

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
