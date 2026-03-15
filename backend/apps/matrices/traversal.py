"""
Shared traversal engine for matrices and item-embedded table fields.

Both global matrices and item-embedded table fields use the same column kinds
and traversal algorithm. This module provides the reusable implementation.
"""
import hashlib

from apps.items.models import CustomFieldDefinition, CustomFieldValue
from apps.relations.models import ItemRelation, RelationType

from .formula import evaluate, extract_references, parse_formula


def run_traversal(non_seed_specs: list[dict], seed_items: list) -> tuple[list[list], set[int], set[int]]:
    """
    Expand rows by following traversal columns starting from seed_items.

    non_seed_specs: list of column spec dicts (all columns except the implicit seed), each with:
        kind: "traversal" | "formula" | "annotation" | "item_field"
        name: str (unique source name, used for formula references)
        For traversal: relation_type_id (str UUID), direction ("outgoing"|"incoming")
        For formula: formula (str)
    seed_items: list of Item ORM objects — rows start as [[seed_item], ...]

    Returns (rows, formula_col_indices, non_traversal_col_indices):
        rows: list of lists where rows[i][0] = seed_item, rows[i][j+1] = non_seed_specs[j] result
              traversal cells: Item object or None
              formula/annotation/item_field cells: None (caller fills these in)
        formula_col_indices: set of absolute row indices (0-based) for formula cells
        non_traversal_col_indices: set of absolute row indices for formula + annotation + item_field
    """
    if not seed_items:
        return [], set(), set()

    # Batch-load all relation types referenced by traversal columns
    rel_type_ids = {
        str(spec["relation_type_id"])
        for spec in non_seed_specs
        if spec.get("kind") == "traversal" and spec.get("relation_type_id")
    }
    rel_type_map = {
        str(rt.id): rt
        for rt in RelationType.objects.filter(id__in=rel_type_ids)
    } if rel_type_ids else {}

    rows = [[item] for item in seed_items]
    formula_col_indices: set[int] = set()
    non_traversal_col_indices: set[int] = set()

    for spec in non_seed_specs:
        col_idx = len(rows[0]) if rows else 1  # absolute index in each row
        kind = spec.get("kind", "traversal")

        if kind == "formula":
            formula_col_indices.add(col_idx)
            non_traversal_col_indices.add(col_idx)
            rows = [row + [None] for row in rows]
            continue

        if kind in ("annotation", "item_field"):
            non_traversal_col_indices.add(col_idx)
            rows = [row + [None] for row in rows]
            continue

        # traversal
        if not spec.get("relation_type_id") or not spec.get("direction"):
            non_traversal_col_indices.add(col_idx)
            rows = [row + [None] for row in rows]
            continue

        rel_type = rel_type_map.get(str(spec["relation_type_id"]))
        if not rel_type:
            non_traversal_col_indices.add(col_idx)
            rows = [row + [None] for row in rows]
            continue

        direction = spec["direction"]
        new_rows = []

        for row in rows:
            # Find the most recent traversal item (skip formula/annotation/item_field cells)
            last_item = None
            for i in range(len(row) - 1, -1, -1):
                if i not in non_traversal_col_indices and row[i] is not None:
                    last_item = row[i]
                    break

            if last_item is None:
                new_rows.append(row + [None])
                continue

            if direction == "outgoing":
                rels = ItemRelation.objects.filter(
                    relation_type=rel_type,
                    source=last_item,
                ).select_related("target", "target__item_type")
                matched = [r.target for r in rels]
            else:
                rels = ItemRelation.objects.filter(
                    relation_type=rel_type,
                    target=last_item,
                ).select_related("source", "source__item_type")
                matched = [r.source for r in rels]

            if matched:
                for m in matched:
                    new_rows.append(row + [m])
            else:
                new_rows.append(row + [None])

        rows = new_rows

    return rows, formula_col_indices, non_traversal_col_indices


def compute_row_hash(row: list, non_traversal_col_indices: set[int]) -> str:
    """
    Compute a stable SHA-256 hash for a row based on its traversal cell item IDs.
    Only seed and traversal cells (not formula/annotation/item_field) contribute to the hash.
    """
    parts = []
    for i, cell in enumerate(row):
        if i not in non_traversal_col_indices:
            parts.append(str(cell.id) if cell is not None else "null")
    return hashlib.sha256(":".join(parts).encode()).hexdigest()


def to_numeric(raw_value, field_def) -> float | None:
    """Convert a custom field value to a float for formula evaluation."""
    if raw_value is None:
        return None

    if field_def and field_def.field_kind == "choice":
        choices = (field_def.options or {}).get("choices", [])
        if raw_value in choices:
            return float(choices.index(raw_value) + 1)
        return None

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def evaluate_formulas(
    all_specs: list[dict],
    rows: list[list],
    formula_col_indices: set[int],
    non_traversal_col_indices: set[int],
) -> None:
    """
    Evaluate formula columns in-place.

    all_specs: list of ALL column specs including the implicit seed (seed at index 0).
               Each spec must have a "name" key for formula reference resolution.
               For global matrices: [seed_spec, src1_spec, src2_spec, ...]
               For item-embedded: [dummy_seed_spec, src0_spec, src1_spec, ...]
    rows: list of lists (rows[i][0] = seed item, rows[i][j+1] = all_specs[j+1] result)
    formula_col_indices: set of absolute row indices for formula cells
    non_traversal_col_indices: set of absolute row indices for formula+annotation+item_field
    """
    if not formula_col_indices or not rows:
        return

    # Map $source_name → absolute row index
    name_to_row_idx = {spec["name"]: i for i, spec in enumerate(all_specs)}

    for col_idx in sorted(formula_col_indices):
        if col_idx >= len(all_specs):
            continue
        spec = all_specs[col_idx]
        formula = spec.get("formula", "")
        if not formula:
            continue

        ast = parse_formula(formula)
        refs = extract_references(ast)
        if not refs:
            continue

        # Collect item IDs for referenced sources
        ref_source_names = {r[0] for r in refs}
        ref_slugs = {r[1] for r in refs}
        item_ids_by_ref_name: dict[str, set] = {}
        for ref_name in ref_source_names:
            row_idx = name_to_row_idx.get(ref_name)
            if row_idx is None or row_idx in formula_col_indices:
                continue
            ids = set()
            for row in rows:
                cell = row[row_idx] if row_idx < len(row) else None
                if cell is not None and hasattr(cell, "id"):
                    ids.add(cell.id)
            item_ids_by_ref_name[ref_name] = ids

        all_item_ids = set()
        for ids in item_ids_by_ref_name.values():
            all_item_ids |= ids

        if not all_item_ids:
            continue

        field_defs = {
            fd.slug: fd
            for fd in CustomFieldDefinition.objects.filter(slug__in=ref_slugs)
        }

        cfvs = CustomFieldValue.objects.filter(
            item_id__in=all_item_ids,
            field_definition__slug__in=ref_slugs,
        ).select_related("field_definition")

        raw_values: dict[tuple, object] = {}
        for cfv in cfvs:
            raw_values[(cfv.item_id, cfv.field_definition.slug)] = cfv.value

        for row in rows:
            context: dict[tuple, float | None] = {}
            has_missing = False
            for ref_name, slug in refs:
                row_idx = name_to_row_idx.get(ref_name)
                if row_idx is None or row_idx in formula_col_indices:
                    has_missing = True
                    break
                cell = row[row_idx] if row_idx < len(row) else None
                if cell is None or not hasattr(cell, "id"):
                    has_missing = True
                    break
                raw = raw_values.get((cell.id, slug))
                context[(ref_name, slug)] = to_numeric(raw, field_defs.get(slug))

            if has_missing:
                row[col_idx] = None
            else:
                row[col_idx] = evaluate(ast, context)
