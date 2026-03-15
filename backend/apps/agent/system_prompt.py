"""Build the dynamic system prompt for agent conversations."""

from __future__ import annotations

from apps.items.models import ItemType, CustomFieldDefinition
from apps.relations.models import RelationType


def build_system_prompt(vault, user, context_item=None) -> str:
    role = user.get_vault_role() or "unknown"

    # Item types with fields
    item_types = ItemType.objects.filter(vault=vault, is_active=True).prefetch_related("custom_fields")
    type_lines = []
    for it in item_types:
        fields = it.custom_fields.all()
        if fields:
            field_strs = [
                f"{f.name} ({f.field_kind}{', required' if f.is_required else ''})"
                for f in fields
            ]
            type_lines.append(f"- {it.name} (slug: {it.slug}) — fields: {', '.join(field_strs)}")
        else:
            type_lines.append(f"- {it.name} (slug: {it.slug})")

    # Relation types
    rel_types = RelationType.objects.filter(vault=vault, is_active=True)
    rel_lines = []
    for rt in rel_types:
        constraints = []
        if rt.source_item_type:
            constraints.append(f"source: {rt.source_item_type.name}")
        if rt.target_item_type:
            constraints.append(f"target: {rt.target_item_type.name}")
        constraint_str = f" [{', '.join(constraints)}]" if constraints else ""
        rel_lines.append(
            f"- {rt.name} ({rt.kind}): {rt.forward_label} / {rt.reverse_label}{constraint_str}"
        )

    parts = [
        f'You are an AI assistant for Verity, a traceability management system.',
        f'Vault: "{vault.name}" | User role: {role}',
        "",
        "Item types:",
        *type_lines,
        "",
        "Relation types:",
        *rel_lines,
    ]

    if context_item:
        parts.extend([
            "",
            f"Current item: {context_item.title} (id: {context_item.id}, "
            f"type: {context_item.item_type.slug}), "
            f"status: {context_item.status}, version: {context_item.current_version}",
        ])

    parts.extend([
        "",
        "You can search and read items freely. Write operations (create/update items, create relations) "
        "require user confirmation before they are executed. When you call a write tool, a pending action "
        "is created that the user must accept or reject.",
        "",
        "Keep responses concise and focused on the user's question.",
    ])

    return "\n".join(parts)
