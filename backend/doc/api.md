# Verity Backend API Documentation

Base URL: `/api/v1/`

All endpoints return JSON. Authentication is via JWT tokens (Bearer scheme) unless noted otherwise.

---

## Table of Contents

1. [Authentication & Users](#authentication--users)
2. [Vaults](#vaults)
3. [Item Types](#item-types)
4. [Items](#items)
5. [Relations](#relations)
6. [Navigation](#navigation)
7. [Traceability Matrices](#traceability-matrices)
8. [Mailbox](#mailbox)
9. [Permissions & Roles](#permissions--roles)
10. [Data Model Concepts](#data-model-concepts)

---

## Authentication & Users

### Site Settings

#### `GET /api/v1/auth/settings/`

Returns public site configuration. **No authentication required.**

**Response:**

```json
{
  "registration_enabled": true,
  "mailbox_limit": 0
}
```

| Field                  | Type    | Description                              |
|------------------------|---------|------------------------------------------|
| `registration_enabled` | boolean | Whether self-registration is open        |
| `mailbox_limit`        | integer | Max mailbox artifacts per user (0 = unlimited) |

#### `PATCH /api/v1/auth/settings/`

Update site settings. **Requires: Site Admin.**

**Request body:** any subset of the fields from `GET`.

---

### Registration & Login

#### `POST /api/v1/auth/register/`

Create a new user account. **No authentication required.** Only works when `registration_enabled` is `true`.

**Request:**

```json
{
  "username": "string (required)",
  "email": "string (required)",
  "password": "string (required, min 8 chars)"
}
```

**Response (201):**

```json
{
  "id": 1,
  "username": "jdoe",
  "email": "jdoe@example.com"
}
```

#### `POST /api/v1/auth/login/`

Obtain a JWT token pair. **No authentication required.**

**Request:**

```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**

```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

#### `POST /api/v1/auth/refresh/`

Refresh an access token. **No authentication required.**

**Request:**

```json
{
  "refresh": "eyJ..."
}
```

**Response:**

```json
{
  "access": "eyJ..."
}
```

---

### Current User

#### `GET /api/v1/auth/me/`

Get the authenticated user's profile. **Requires: Authenticated.**

**Response:**

```json
{
  "id": 1,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "is_site_admin": false,
  "vault_role": "editor",
  "date_joined": "2025-01-15T10:30:00Z",
  "active_vault": "uuid",
  "active_vault_name": "My Vault",
  "active_vault_locked": false
}
```

| Field                | Type         | Description                                      |
|----------------------|--------------|--------------------------------------------------|
| `vault_role`         | string/null  | Role in active vault: `viewer`, `editor`, `admin`, or `null` |
| `active_vault`       | uuid/null    | Currently selected vault                         |
| `active_vault_name`  | string/null  | Name of active vault                             |
| `active_vault_locked`| boolean/null | Whether active vault is locked                   |

#### `PATCH /api/v1/auth/me/`

Update the authenticated user's profile (username, email). **Requires: Authenticated.**

#### `POST /api/v1/auth/me/password/`

Change own password. **Requires: Authenticated.**

**Request:**

```json
{
  "current_password": "string (required)",
  "new_password": "string (required, min 8 chars)"
}
```

---

### User Management (Site Admin)

#### `GET /api/v1/auth/users/`

List all users. **Requires: Site Admin or Vault Admin.**

**Response:** array of:

```json
{
  "id": 1,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "is_site_admin": false,
  "date_joined": "2025-01-15T10:30:00Z",
  "account_status": "active",
  "is_active": true
}
```

| Field            | Type   | Values                          |
|------------------|--------|---------------------------------|
| `account_status` | string | `active`, `locked`, `deleted`   |

#### `POST /api/v1/auth/users/create/`

Create a user (admin-initiated). **Requires: Site Admin.**

**Request:**

```json
{
  "username": "string",
  "email": "string",
  "password": "string (min 8 chars)",
  "is_site_admin": false
}
```

#### `GET /api/v1/auth/users/{id}/`

Retrieve a specific user. **Requires: Site Admin.**

#### `PATCH /api/v1/auth/users/{id}/`

Update a user. **Requires: Site Admin.**

#### `POST /api/v1/auth/users/{id}/password/`

Reset a user's password. **Requires: Site Admin.**

**Request:**

```json
{
  "new_password": "string (min 8 chars)"
}
```

#### `POST /api/v1/auth/users/{id}/lock/`

Lock a user account (prevents login). **Requires: Site Admin.**

#### `POST /api/v1/auth/users/{id}/unlock/`

Unlock a user account. **Requires: Site Admin.**

#### `POST /api/v1/auth/users/{id}/delete/`

Soft-delete a user account. **Requires: Site Admin.**

---

## Vaults

Vaults are isolated workspaces that scope all data (items, relations, matrices, etc.).

### `GET /api/v1/vaults/`

List all vaults. **Requires: Site Admin.**

**Response:** array of:

```json
{
  "id": "uuid",
  "name": "string",
  "slug": "string",
  "description": "string",
  "created_by": 1,
  "created_by_username": "admin",
  "member_count": 5,
  "is_locked": false,
  "locked_at": null,
  "locked_by": null,
  "locked_by_username": null,
  "created_at": "2025-01-15T10:30:00Z",
  "my_role": "admin"
}
```

### `POST /api/v1/vaults/`

Create a new vault. **Requires: Site Admin.**

**Request:**

```json
{
  "name": "string (required)",
  "slug": "string (optional, auto-generated from name)",
  "description": "string (optional)"
}
```

On creation, two built-in relation types are automatically created: `is_composed_of` (composition) and `traces_to` (trace).

### `GET /api/v1/vaults/{id}/`

Retrieve vault details. **Requires: Site Admin.**

### `PATCH /api/v1/vaults/{id}/`

Update a vault. **Requires: Site Admin.**

### `DELETE /api/v1/vaults/{id}/`

Soft-delete a vault. **Requires: Site Admin.**

### `GET /api/v1/vaults/my/`

List vaults the current user is a member of. **Requires: Authenticated.**

### `POST /api/v1/vaults/select/`

Set the user's active vault. **Requires: Authenticated.**

**Request:**

```json
{
  "vault_id": "uuid"
}
```

### `POST /api/v1/vaults/{id}/lock/`

Lock a vault (blocks all write operations). **Requires: Site Admin or Vault Admin.**

### `POST /api/v1/vaults/{id}/unlock/`

Unlock a vault. **Requires: Site Admin or Vault Admin.**

---

### Vault Members

#### `GET /api/v1/vaults/{vault_id}/members/`

List vault members. **Requires: Site Admin or Vault Admin.**

**Response:** array of:

```json
{
  "id": "uuid",
  "vault": "uuid",
  "user": 1,
  "username": "jdoe",
  "email": "jdoe@example.com",
  "role": "editor",
  "is_site_admin": false,
  "created_at": "2025-01-15T10:30:00Z"
}
```

| Field  | Type   | Values                        |
|--------|--------|-------------------------------|
| `role` | string | `viewer`, `editor`, `admin`   |

#### `POST /api/v1/vaults/{vault_id}/members/`

Add a member to the vault. **Requires: Site Admin or Vault Admin.**

**Request:**

```json
{
  "user": 1,
  "role": "editor"
}
```

#### `GET /api/v1/vaults/{vault_id}/members/{membership_id}/`

Retrieve a membership. **Requires: Site Admin or Vault Admin.**

#### `PATCH /api/v1/vaults/{vault_id}/members/{membership_id}/`

Update a member's role. **Requires: Site Admin or Vault Admin.**

#### `DELETE /api/v1/vaults/{vault_id}/members/{membership_id}/`

Remove a member from the vault. **Requires: Site Admin or Vault Admin.**

---

### Vault Audit Log

#### `GET /api/v1/vaults/{vault_id}/audit-log/`

List audit log entries for a vault. **Requires: Site Admin or Vault Admin.**

**Response:** array of:

```json
{
  "id": "uuid",
  "vault": "uuid",
  "event": "member_added",
  "actor": 1,
  "actor_username": "admin",
  "detail": { "username": "jdoe", "role": "editor" },
  "created_at": "2025-01-15T10:30:00Z"
}
```

| Event                  | Description                    |
|------------------------|--------------------------------|
| `vault_created`        | Vault was created              |
| `member_added`         | Member added to vault          |
| `member_removed`       | Member removed from vault      |
| `member_role_changed`  | Member's role was changed      |
| `vault_locked`         | Vault was locked               |
| `vault_unlocked`       | Vault was unlocked             |

---

## Item Types

All item-type endpoints require an active vault. **Requires: HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked.**

### `GET /api/v1/item-types/`

List all item types in the active vault.

**Response:** array of:

```json
{
  "id": "uuid",
  "name": "Requirement",
  "slug": "requirement",
  "description": "A system requirement",
  "icon": "file-text",
  "is_active": true,
  "custom_fields": [ ... ],
  "item_count": 42
}
```

### `POST /api/v1/item-types/`

Create a new item type.

**Request:**

```json
{
  "name": "string (required)",
  "slug": "string (optional, auto-generated)",
  "description": "string (optional)",
  "icon": "string (optional)"
}
```

### `GET /api/v1/item-types/{id}/`

Retrieve an item type with its custom field definitions.

### `PATCH /api/v1/item-types/{id}/`

Update an item type.

### `DELETE /api/v1/item-types/{id}/`

Soft-delete an item type and its custom field definitions.

---

### Custom Field Definitions

#### `POST /api/v1/item-types/{id}/custom-fields`

Add a custom field definition to an item type.

**Request:**

```json
{
  "name": "Priority",
  "slug": "priority",
  "field_kind": "choice",
  "is_required": false,
  "options": { "choices": ["Low", "Medium", "High"] },
  "display_order": 1
}
```

| Field          | Type    | Values                                              |
|----------------|---------|-----------------------------------------------------|
| `field_kind`   | string  | `text`, `integer`, `decimal`, `boolean`, `date`, `choice` |
| `is_required`  | boolean | Whether the field must be filled                    |
| `options`      | object  | For `choice` kind: `{"choices": ["A", "B", "C"]}`  |
| `display_order`| integer | Ordering position among fields                      |

#### `PATCH /api/v1/item-types/{id}/custom-fields/{field_id}`

Update a custom field definition.

#### `DELETE /api/v1/item-types/{id}/custom-fields/{field_id}`

Soft-delete a custom field definition and all its values.

---

### Document Templates

Templates define Markdown output format for items of a given type. Template variables use `{{field_slug}}` syntax including `{{title}}`, `{{description}}`, and any custom field slugs.

#### `GET /api/v1/item-types/{id}/template`

Get the document template for an item type.

#### `PUT /api/v1/item-types/{id}/template`

Create or update the document template.

**Request:**

```json
{
  "template": "# {{title}}\n\n{{description}}\n\nPriority: {{priority}}"
}
```

#### `DELETE /api/v1/item-types/{id}/template`

Remove the document template.

---

## Items

All item endpoints require an active vault. **Requires: HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked.**

### `GET /api/v1/items/`

List items in the active vault. Supports filtering, search, and ordering.

**Query Parameters:**

| Parameter          | Type   | Description                                    |
|--------------------|--------|------------------------------------------------|
| `item_type__slug`  | string | Filter by item type slug                       |
| `status`           | string | Filter by status                               |
| `created_by`       | int    | Filter by creator user ID                      |
| `search`           | string | Search in `title` and `description`            |
| `ordering`         | string | Order by: `title`, `created_at`, `updated_at`, `status` (prefix `-` for descending) |

**Response:** array of:

```json
{
  "id": "uuid",
  "title": "REQ-001: Login",
  "status": "active",
  "item_type": "uuid",
  "item_type_name": "Requirement",
  "item_type_slug": "requirement",
  "created_by": 1,
  "created_by_username": "jdoe",
  "current_version": 3,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-02-01T14:00:00Z"
}
```

### `POST /api/v1/items/`

Create a new item.

**Request:**

```json
{
  "title": "string (required)",
  "description": "string (optional)",
  "status": "draft",
  "item_type": "uuid (required)",
  "custom_fields": {
    "priority": "High",
    "due_date": "2025-06-01"
  }
}
```

| Status Values |
|---------------|
| `draft`       |
| `active`      |
| `in_review`   |
| `approved`    |
| `archived`    |

### `GET /api/v1/items/{id}/`

Retrieve a single item with full details including custom fields.

**Response:**

```json
{
  "id": "uuid",
  "title": "REQ-001: Login",
  "description": "The system shall support user login.",
  "status": "active",
  "item_type": "uuid",
  "item_type_name": "Requirement",
  "created_by": 1,
  "created_by_username": "jdoe",
  "custom_fields": {
    "priority": "High",
    "due_date": "2025-06-01"
  },
  "current_version": 3,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-02-01T14:00:00Z"
}
```

### `PATCH /api/v1/items/{id}/`

Update an item. Each update increments `current_version` and creates a version snapshot.

**Request:** any subset of `title`, `description`, `status`, `custom_fields`.

### `DELETE /api/v1/items/{id}/`

Soft-delete an item and its versions, custom field values, and relations.

---

### Item Tree Operations

#### `GET /api/v1/items/roots/`

Get root-level items (items with no composition parent) in the active vault.

**Response:** array of:

```json
{
  "id": "uuid",
  "title": "System Requirements",
  "item_type_slug": "document",
  "child_count": 5,
  "position": 0,
  "has_suspect_links": false,
  "has_suspect_descendants": true
}
```

#### `GET /api/v1/items/{id}/children`

Get the composition children of an item.

**Response:** array of tree node objects (same structure as `roots`).

#### `POST /api/v1/items/{id}/reorder-children`

Reorder the composition children of an item.

**Request:**

```json
{
  "order": ["uuid-1", "uuid-2", "uuid-3"]
}
```

#### `GET /api/v1/items/{id}/ancestors`

Get the ancestor chain from the item up to the root (composition hierarchy).

---

### Item Versions

#### `GET /api/v1/items/{id}/versions`

List all version snapshots for an item.

**Response:** array of:

```json
{
  "id": "uuid",
  "version_number": 2,
  "title": "REQ-001: Login",
  "description": "Original description",
  "status": "draft",
  "custom_fields_snapshot": { "priority": "Medium" },
  "created_by": 1,
  "created_by_username": "jdoe",
  "created_at": "2025-01-20T09:00:00Z",
  "change_summary": "Updated status to active"
}
```

#### `GET /api/v1/items/{id}/versions/{version_number}`

Retrieve a specific version snapshot.

---

## Relations

All relation endpoints require an active vault. **Requires: HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked.**

### Relation Types

#### `GET /api/v1/relation-types/`

List relation types in the active vault.

**Response:** array of:

```json
{
  "id": "uuid",
  "kind": "trace",
  "name": "traces_to",
  "forward_label": "traces to",
  "reverse_label": "traced by",
  "description": "Trace relation between items",
  "source_item_type": "uuid or null",
  "source_item_type_name": "Requirement",
  "target_item_type": "uuid or null",
  "target_item_type_name": "Test Case",
  "is_builtin": true,
  "is_active": true
}
```

| Field               | Type      | Description                                       |
|---------------------|-----------|---------------------------------------------------|
| `kind`              | string    | `composition` or `trace`                          |
| `source_item_type`  | uuid/null | Restrict source items to this type (null = any)   |
| `target_item_type`  | uuid/null | Restrict target items to this type (null = any)   |
| `is_builtin`        | boolean   | Built-in types (`is_composed_of`, `traces_to`) cannot be deleted |

#### `POST /api/v1/relation-types/`

Create a new relation type.

**Request:**

```json
{
  "kind": "trace",
  "name": "satisfies",
  "forward_label": "satisfies",
  "reverse_label": "satisfied by",
  "description": "Links requirements to design elements",
  "source_item_type": "uuid or null",
  "target_item_type": "uuid or null"
}
```

#### `GET /api/v1/relation-types/{id}/`

Retrieve a relation type.

#### `PATCH /api/v1/relation-types/{id}/`

Update a relation type.

#### `DELETE /api/v1/relation-types/{id}/`

Soft-delete a relation type. Fails for built-in types.

---

### Item Relations

#### `GET /api/v1/relations/`

List relations in the active vault. Supports filtering.

**Query Parameters:**

| Parameter       | Type | Description                     |
|-----------------|------|---------------------------------|
| `relation_type` | uuid | Filter by relation type         |
| `source`        | uuid | Filter by source item           |
| `target`        | uuid | Filter by target item           |

**Response:** array of:

```json
{
  "id": "uuid",
  "relation_type": "uuid",
  "relation_type_name": "traces_to",
  "forward_label": "traces to",
  "reverse_label": "traced by",
  "source": "uuid",
  "source_title": "REQ-001",
  "source_type_slug": "requirement",
  "source_version": 3,
  "target": "uuid",
  "target_title": "TC-001",
  "target_type_slug": "test-case",
  "target_version": 1,
  "version_pinned": false,
  "created_by": 1,
  "created_at": "2025-01-15T10:30:00Z"
}
```

#### `POST /api/v1/relations/`

Create a relation between two items. `source_version` and `target_version` are automatically set to each item's `current_version`.

**Request:**

```json
{
  "relation_type": "uuid (required)",
  "source": "uuid (required)",
  "target": "uuid (required)"
}
```

#### `GET /api/v1/relations/{id}/`

Retrieve a relation.

#### `PATCH /api/v1/relations/{id}/`

Update a relation.

#### `DELETE /api/v1/relations/{id}/`

Soft-delete a relation.

#### `POST /api/v1/relations/{id}/confirm/`

Confirm a suspect relation, resetting version tracking to current.

**Request (all fields optional):**

```json
{
  "source_version": 5,
  "target_version": 3,
  "version_pinned": false
}
```

If `source_version` or `target_version` are omitted, they default to the item's `current_version`. Setting `version_pinned` to `true` indicates the user intentionally acknowledges the version difference.

---

## Navigation

### `GET /api/v1/items/{id}/navigation/`

Get the spatial navigation context for an item. **Requires: HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked.**

This is the primary endpoint for the item navigator UI. It returns the item's position in both the composition hierarchy and the trace graph.

**Response:**

```json
{
  "parent": { ... } or null,
  "children": [ ... ],
  "siblings": [ ... ],
  "left": [ ... ],
  "right": [ ... ]
}
```

**`parent`, `children`, `siblings`** — composition hierarchy refs:

```json
{
  "id": "uuid",
  "title": "string",
  "item_type_slug": "string",
  "pinned_version": null,
  "current_version": 3,
  "self_pinned_version": null,
  "self_current_version": 2,
  "is_suspect": false,
  "other_changed": false,
  "self_changed": false,
  "is_version_pinned": false
}
```

**`left`** (incoming trace relations) and **`right`** (outgoing trace relations):

```json
{
  "id": "uuid",
  "title": "string",
  "item_type_slug": "string",
  "pinned_version": 1,
  "current_version": 3,
  "self_pinned_version": 2,
  "self_current_version": 5,
  "is_suspect": true,
  "other_changed": true,
  "self_changed": true,
  "is_version_pinned": false,
  "relation_id": "uuid",
  "relation_type": "uuid",
  "relation_label": "traces to"
}
```

**Suspect link fields explained:**

| Field                 | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| `pinned_version`      | The version of the *other* item stored on the relation         |
| `current_version`     | The *other* item's current version                             |
| `self_pinned_version` | The version of the *current* item stored on the relation       |
| `self_current_version`| The *current* item's current version                           |
| `is_suspect`          | `true` if either side changed since the relation was confirmed |
| `other_changed`       | `true` if the other item was edited after relation confirmed   |
| `self_changed`        | `true` if the current item was edited after relation confirmed |
| `is_version_pinned`   | `true` if user explicitly pinned the relation to a version     |

---

## Traceability Matrices

Matrices provide configurable table views that follow relations through the item graph. **Requires: HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked.**

### `GET /api/v1/tables/`

List matrices in the active vault.

### `POST /api/v1/tables/`

Create a new matrix with column definitions.

**Request:**

```json
{
  "name": "Requirements Traceability",
  "description": "Maps requirements to test cases",
  "columns": [
    {
      "position": 0,
      "label": "Requirements",
      "column_kind": "seed",
      "seed_item_type": "uuid",
      "seed_container": "uuid (optional)"
    },
    {
      "position": 1,
      "label": "Test Cases",
      "column_kind": "traversal",
      "relation_type": "uuid",
      "direction": "outgoing"
    }
  ]
}
```

**Column configuration:**

| Field             | Type      | Description                                          |
|-------------------|-----------|------------------------------------------------------|
| `position`        | integer   | Column position (0 = seed column, required)          |
| `label`           | string    | Display label                                        |
| `column_kind`     | string    | `seed`, `traversal`, or `formula`                    |
| `seed_item_type`  | uuid      | *Seed only:* item type to seed the rows              |
| `seed_container`  | uuid/null | *Seed only:* optional parent item to scope seed items |
| `relation_type`   | uuid      | *Traversal only:* relation type to follow            |
| `direction`       | string    | *Traversal only:* `outgoing` or `incoming`           |
| `formula`         | string    | *Formula only:* formula expression                   |

**Validation rules:**
- Position 0 must be `seed` kind and requires `seed_item_type`
- Positions > 0 with `traversal` kind require `relation_type` and `direction`
- `formula` kind requires a `formula` expression

### `GET /api/v1/tables/{id}/`

Retrieve a matrix with its column definitions.

**Response:**

```json
{
  "id": "uuid",
  "name": "Requirements Traceability",
  "description": "Maps requirements to test cases",
  "created_by": 1,
  "created_by_username": "admin",
  "columns": [
    {
      "id": "uuid",
      "position": 0,
      "label": "Requirements",
      "column_kind": "seed",
      "seed_item_type": "uuid",
      "seed_item_type_name": "Requirement",
      "seed_container": null,
      "seed_container_title": null,
      "relation_type": null,
      "relation_type_name": null,
      "relation_forward_label": null,
      "relation_reverse_label": null,
      "direction": null,
      "formula": ""
    }
  ],
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-02-01T14:00:00Z"
}
```

### `PATCH /api/v1/tables/{id}/`

Update a matrix and its columns.

### `DELETE /api/v1/tables/{id}/`

Soft-delete a matrix and its columns.

### `GET /api/v1/tables/{id}/data`

Execute the matrix and return computed table data.

**Response:**

```json
{
  "columns": [
    {
      "position": 0,
      "label": "Requirements",
      "kind": "seed"
    },
    {
      "position": 1,
      "label": "Test Cases",
      "kind": "traversal"
    }
  ],
  "rows": [
    [
      {
        "id": "uuid",
        "title": "REQ-001: Login",
        "item_type_name": "Requirement",
        "item_type_slug": "requirement"
      },
      {
        "id": "uuid",
        "title": "TC-001: Login Test",
        "item_type_name": "Test Case",
        "item_type_slug": "test-case"
      }
    ]
  ]
}
```

Each row is an array of cell objects (one per column). Cells may be `null` if no related item exists for that traversal step.

---

## Mailbox

Per-user generated Markdown documents from item templates. **Requires: Authenticated.**

### `GET /api/v1/mailbox/`

List the current user's mailbox artifacts.

**Response:** array of:

```json
{
  "id": "uuid",
  "filename": "REQ-001.md",
  "file_size": 1024,
  "content_type": "text/markdown",
  "source_item": "uuid",
  "vault": "uuid",
  "vault_name": "My Vault",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### `GET /api/v1/mailbox/{id}/`

Retrieve a mailbox artifact including its content.

**Response:**

```json
{
  "id": "uuid",
  "filename": "REQ-001.md",
  "content": "# REQ-001: Login\n\nThe system shall...",
  "file_size": 1024,
  "content_type": "text/markdown",
  "source_item": "uuid",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### `DELETE /api/v1/mailbox/{id}/`

Soft-delete a mailbox artifact.

### `POST /api/v1/mailbox/generate/`

Generate a new Markdown document from an item's template.

**Request:**

```json
{
  "item_id": "uuid (required)"
}
```

The item's type must have a document template configured. The template variables (`{{title}}`, `{{description}}`, custom field slugs) are populated from the item's current data.

---

## Permissions & Roles

### Role Hierarchy

| Role        | Scope  | Capabilities                                               |
|-------------|--------|------------------------------------------------------------|
| Site Admin  | Global | Full system access: manage users, vaults, all data         |
| Vault Admin | Vault  | Manage vault members, lock/unlock vault, view audit logs   |
| Editor      | Vault  | Create, update, delete items, relations, matrices          |
| Viewer      | Vault  | Read-only access to all vault data                         |

### Permission Classes

| Class               | Behavior                                                        |
|---------------------|-----------------------------------------------------------------|
| `IsSiteAdmin`       | Only site administrators                                        |
| `HasVaultAccess`    | User must have an active vault and be a member (or site admin)  |
| `ReadOnlyOrEditor`  | Viewers: GET/HEAD/OPTIONS only; Editors/Admins: all methods     |
| `VaultNotLocked`    | Read operations always pass; write operations blocked if vault is locked |
| `IsVaultAdmin`      | User's role in active vault must be `admin`                     |

### Vault Locking

When a vault is locked:
- All read operations continue to work normally
- All write operations (POST, PATCH, DELETE) on vault-scoped resources are blocked
- Only Site Admins or Vault Admins can lock/unlock

---

## Data Model Concepts

### Soft Delete

All models use soft deletion. Records are never permanently removed from the database. Instead:
- `is_deleted` is set to `true`
- `deleted_at` is set to the current timestamp
- Standard queries (`objects` manager) exclude deleted records
- `all_objects` manager includes deleted records

Deletion cascades through related models (e.g., deleting an item also soft-deletes its versions, custom field values, and relations).

### Versioning & Suspect Links

1. Every `Item` has a `current_version` counter starting at 1
2. Each `PATCH` to an item:
   - Creates an `ItemVersion` snapshot of the pre-update state
   - Increments `current_version`
3. When a relation is created, `source_version` and `target_version` are set to each item's `current_version`
4. A relation becomes **suspect** when either stored version falls behind the linked item's current version
5. Users confirm relations via `POST /relations/{id}/confirm/` which resets versions to current

### Composition vs Trace Relations

| Aspect       | Composition                    | Trace                              |
|--------------|--------------------------------|------------------------------------|
| Purpose      | Defines tree hierarchy         | Defines horizontal traceability    |
| Built-in     | `is_composed_of`               | `traces_to`                        |
| Navigation   | parent / children / siblings   | left (incoming) / right (outgoing) |
| Tree view    | Shown in composition tree      | Not shown in tree                  |
| Ordering     | Uses `position` field          | No ordering                        |
