"""Agent tools for reading and writing vault data.

Read tools execute immediately. Write tools create PendingAction records.
"""

from __future__ import annotations

import uuid

from django.db.models import Q

from apps.items.models import CustomFieldDefinition, CustomFieldValue, Item, ItemType
from apps.relations.models import ItemRelation, RelationType

from .models import PendingAction


# ──────────────────────────── Read-only tools ────────────────────────────


def search_items(vault, user, *, query="", item_type_slug="", status=""):
    """Search items by text, type, and/or status."""
    qs = Item.objects.filter(item_type__vault=vault).select_related("item_type")
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if item_type_slug:
        qs = qs.filter(item_type__slug=item_type_slug)
    if status:
        qs = qs.filter(status=status)
    qs = qs[:25]
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "item_type": item.item_type.slug,
            "status": item.status,
            "current_version": item.current_version,
        }
        for item in qs
    ]


def get_item_detail(vault, user, *, item_id):
    """Get full item detail including custom fields."""
    item = Item.objects.select_related("item_type", "created_by").get(
        id=item_id, item_type__vault=vault
    )
    cfvs = CustomFieldValue.objects.filter(item=item).select_related("field_definition")
    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "item_type": item.item_type.slug,
        "status": item.status,
        "current_version": item.current_version,
        "created_by": item.created_by.username,
        "custom_fields": {
            cfv.field_definition.slug: cfv.value for cfv in cfvs
        },
    }


def get_item_children(vault, user, *, item_id):
    """Get composition children of an item."""
    children = (
        ItemRelation.objects.filter(
            source_id=item_id,
            relation_type__kind=RelationType.Kind.COMPOSITION,
            relation_type__vault=vault,
        )
        .select_related("target", "target__item_type")
        .order_by("position")
    )
    return [
        {
            "id": str(rel.target.id),
            "title": rel.target.title,
            "item_type": rel.target.item_type.slug,
            "status": rel.target.status,
            "position": rel.position,
        }
        for rel in children
    ]


def get_item_relations(vault, user, *, item_id):
    """Get trace relations (incoming and outgoing) for an item."""
    outgoing = (
        ItemRelation.objects.filter(
            source_id=item_id,
            relation_type__kind=RelationType.Kind.TRACE,
            relation_type__vault=vault,
        )
        .select_related("target", "target__item_type", "relation_type")
    )
    incoming = (
        ItemRelation.objects.filter(
            target_id=item_id,
            relation_type__kind=RelationType.Kind.TRACE,
            relation_type__vault=vault,
        )
        .select_related("source", "source__item_type", "relation_type")
    )
    result = {"outgoing": [], "incoming": []}
    for rel in outgoing:
        is_suspect = (
            (rel.source_version is not None and rel.source_version < rel.source.current_version)
            or (rel.target_version is not None and rel.target_version < rel.target.current_version)
        ) and not rel.version_pinned
        result["outgoing"].append({
            "relation_id": str(rel.id),
            "relation_type": rel.relation_type.name,
            "target_id": str(rel.target.id),
            "target_title": rel.target.title,
            "target_type": rel.target.item_type.slug,
            "is_suspect": is_suspect,
        })
    for rel in incoming:
        is_suspect = (
            (rel.source_version is not None and rel.source_version < rel.source.current_version)
            or (rel.target_version is not None and rel.target_version < rel.target.current_version)
        ) and not rel.version_pinned
        result["incoming"].append({
            "relation_id": str(rel.id),
            "relation_type": rel.relation_type.name,
            "source_id": str(rel.source.id),
            "source_title": rel.source.title,
            "source_type": rel.source.item_type.slug,
            "is_suspect": is_suspect,
        })
    return result


def get_item_types(vault, user):
    """List item types with their custom field definitions."""
    item_types = ItemType.objects.filter(vault=vault, is_active=True).prefetch_related(
        "custom_fields"
    )
    return [
        {
            "id": str(it.id),
            "name": it.name,
            "slug": it.slug,
            "custom_fields": [
                {
                    "name": cf.name,
                    "slug": cf.slug,
                    "field_kind": cf.field_kind,
                    "is_required": cf.is_required,
                    "options": cf.options,
                }
                for cf in it.custom_fields.all()
            ],
        }
        for it in item_types
    ]


def get_relation_types(vault, user):
    """List relation types in the vault."""
    rel_types = RelationType.objects.filter(vault=vault, is_active=True)
    return [
        {
            "id": str(rt.id),
            "name": rt.name,
            "kind": rt.kind,
            "forward_label": rt.forward_label,
            "reverse_label": rt.reverse_label,
        }
        for rt in rel_types
    ]


# ──────────────────────────── Write tools ────────────────────────────


def create_item(conversation, message, vault, user, *, item_type_slug, title, description="", status="draft", custom_fields=None):
    """Propose creating a new item. Returns a PendingAction."""
    payload = {
        "item_type_slug": item_type_slug,
        "title": title,
        "description": description,
        "status": status,
        "custom_fields": custom_fields or {},
    }
    action = PendingAction.objects.create(
        conversation=conversation,
        message=message,
        action_type=PendingAction.ActionType.CREATE_ITEM,
        payload=payload,
    )
    return {
        "pending_action_id": str(action.id),
        "action_type": "create_item",
        "status": "pending",
        "message": f"Proposed creating '{title}' ({item_type_slug}). Awaiting user confirmation.",
    }


def update_item(conversation, message, vault, user, *, item_id, title=None, description=None, status=None, custom_fields=None):
    """Propose updating an existing item. Returns a PendingAction."""
    payload = {"item_id": item_id}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if status is not None:
        payload["status"] = status
    if custom_fields is not None:
        payload["custom_fields"] = custom_fields
    action = PendingAction.objects.create(
        conversation=conversation,
        message=message,
        action_type=PendingAction.ActionType.UPDATE_ITEM,
        payload=payload,
    )
    return {
        "pending_action_id": str(action.id),
        "action_type": "update_item",
        "status": "pending",
        "message": f"Proposed updating item {item_id}. Awaiting user confirmation.",
    }


def create_relation(conversation, message, vault, user, *, relation_type_name, source_id, target_id):
    """Propose creating a relation between two items. Returns a PendingAction."""
    payload = {
        "relation_type_name": relation_type_name,
        "source_id": source_id,
        "target_id": target_id,
    }
    action = PendingAction.objects.create(
        conversation=conversation,
        message=message,
        action_type=PendingAction.ActionType.CREATE_RELATION,
        payload=payload,
    )
    return {
        "pending_action_id": str(action.id),
        "action_type": "create_relation",
        "status": "pending",
        "message": f"Proposed creating relation '{relation_type_name}' from {source_id} to {target_id}. Awaiting user confirmation.",
    }


# ──────────────────────────── Tool registry ────────────────────────────

READ_TOOLS = {
    "search_items": search_items,
    "get_item_detail": get_item_detail,
    "get_item_children": get_item_children,
    "get_item_relations": get_item_relations,
    "get_item_types": get_item_types,
    "get_relation_types": get_relation_types,
}

WRITE_TOOLS = {
    "create_item": create_item,
    "update_item": update_item,
    "create_relation": create_relation,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "Search items in the vault by text, item type, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for in title or description."},
                    "item_type_slug": {"type": "string", "description": "Filter by item type slug."},
                    "status": {"type": "string", "description": "Filter by status (draft, active, in_review, approved, archived)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_detail",
            "description": "Get full details of an item including custom fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "UUID of the item."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_children",
            "description": "Get composition children of an item (items composed under it).",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "UUID of the parent item."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_relations",
            "description": "Get trace relations (incoming and outgoing) for an item. Shows which items trace to or from this item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "UUID of the item."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item_types",
            "description": "List all item types in the vault with their custom field definitions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_relation_types",
            "description": "List all relation types in the vault.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_item",
            "description": "Propose creating a new item. This requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_type_slug": {"type": "string", "description": "Slug of the item type."},
                    "title": {"type": "string", "description": "Title for the new item."},
                    "description": {"type": "string", "description": "Description/body of the item."},
                    "status": {"type": "string", "description": "Status (draft, active, in_review, approved, archived). Defaults to draft."},
                    "custom_fields": {"type": "object", "description": "Custom field values as {slug: value}."},
                },
                "required": ["item_type_slug", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_item",
            "description": "Propose updating an existing item. This requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "UUID of the item to update."},
                    "title": {"type": "string", "description": "New title."},
                    "description": {"type": "string", "description": "New description."},
                    "status": {"type": "string", "description": "New status."},
                    "custom_fields": {"type": "object", "description": "Custom field values to update as {slug: value}."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_relation",
            "description": "Propose creating a relation between two items. This requires user confirmation before execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relation_type_name": {"type": "string", "description": "Name of the relation type (e.g. 'traces_to', 'is_composed_of')."},
                    "source_id": {"type": "string", "description": "UUID of the source item."},
                    "target_id": {"type": "string", "description": "UUID of the target item."},
                },
                "required": ["relation_type_name", "source_id", "target_id"],
            },
        },
    },
]
