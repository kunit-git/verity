# Verity Data Model & Permissions

This document describes the permission system, role hierarchy, and core data model concepts used throughout the Verity backend.

---

## Table of Contents

1. [Permissions & Roles](#permissions--roles)
2. [Vault Locking](#vault-locking)
3. [Soft Delete](#soft-delete)
4. [Versioning & Suspect Links](#versioning--suspect-links)
5. [Composition vs Trace Relations](#composition-vs-trace-relations)

---

## Permissions & Roles

### Role Hierarchy

| Role        | Scope  | Capabilities                                               |
|-------------|--------|------------------------------------------------------------|
| Site Admin  | Global | Full system access: manage users, vaults, all data         |
| Vault Admin | Vault  | Manage vault members, lock/unlock vault, view audit logs   |
| Editor      | Vault  | Create, update, delete items, relations, matrices          |
| Viewer      | Vault  | Read-only access to all vault data                         |

Site Admin is a global flag on the user account (`is_site_admin`). The other three roles are per-vault, assigned through vault membership.

### Permission Classes

The backend uses the following Django REST Framework permission classes to enforce access control:

| Class               | Behavior                                                        |
|---------------------|-----------------------------------------------------------------|
| `IsSiteAdmin`       | Only site administrators                                        |
| `HasVaultAccess`    | User must have an active vault and be a member (or site admin)  |
| `ReadOnlyOrEditor`  | Viewers: GET/HEAD/OPTIONS only; Editors/Admins: all methods     |
| `VaultNotLocked`    | Read operations always pass; write operations blocked if vault is locked |
| `IsVaultAdmin`      | User's role in active vault must be `admin`                     |

Most vault-scoped endpoints combine multiple classes. The typical stack is:

```
HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked
```

This ensures the user belongs to the vault, has the right role for the HTTP method, and the vault is not locked for write operations.

### How Roles Are Resolved

1. **Site Admin** — checked via `User.is_site_admin`. Site admins bypass vault membership checks and can access all vaults.
2. **Vault Role** — determined by the `VaultMembership` record linking the user to their active vault. The `role` field holds `viewer`, `editor`, or `admin`.
3. **Active Vault** — each user has an `active_vault` field. All vault-scoped API requests operate against this vault. Users switch vaults via `POST /api/v1/vaults/select/`.

---

## Vault Locking

Vaults can be locked to prevent all write operations while preserving read access.

When a vault is locked:

- All read operations (GET, HEAD, OPTIONS) continue to work normally
- All write operations (POST, PATCH, DELETE) on vault-scoped resources are blocked with a `403 Forbidden` response
- Only Site Admins or Vault Admins can lock/unlock a vault

Locking is tracked on the vault record:

| Field              | Type          | Description                          |
|--------------------|---------------|--------------------------------------|
| `is_locked`        | boolean       | Whether the vault is currently locked |
| `locked_at`        | datetime/null | When the vault was locked            |
| `locked_by`        | user/null     | Who locked the vault                 |

Lock and unlock events are recorded in the vault's audit log.

---

## Soft Delete

All models use soft deletion. Records are never permanently removed from the database. Instead:

- `is_deleted` is set to `true`
- `deleted_at` is set to the current timestamp

### Managers

| Manager        | Behavior                          |
|----------------|-----------------------------------|
| `objects`      | Default — excludes deleted records |
| `all_objects`  | Includes deleted records          |

### Cascade Behavior

Deletion cascades through related models:

- **Item** → soft-deletes its `ItemVersion` records, `CustomFieldValue` records, and `ItemRelation` records
- **ItemType** → soft-deletes its `CustomFieldDefinition` records
- **Vault** → soft-deletes all contained data
- **User** → soft-deleted (account status set to `deleted`)

---

## Versioning & Suspect Links

### Item Versioning

Every `Item` has a `current_version` counter starting at 1. Each update to an item follows this sequence:

1. A `PATCH` request arrives for the item
2. An `ItemVersion` snapshot is created capturing the **pre-update** state (title, description, status, custom fields)
3. The update is applied to the item
4. `current_version` is incremented

Version snapshots preserve the complete item state at each point in time, enabling full audit history.

### Suspect Link Detection

Relations track the version of each linked item at the time the relation was last confirmed:

| Field            | Description                                                |
|------------------|------------------------------------------------------------|
| `source_version` | Version of the source item when the relation was confirmed |
| `target_version` | Version of the target item when the relation was confirmed |

A relation becomes **suspect** when either stored version falls behind the linked item's current version — meaning one side was edited after the relation was last confirmed.

**Example:**

```
Relation created:  source_version=2, target_version=1
Source item edited: source.current_version becomes 3
→ Relation is now suspect (source_version 2 < current_version 3)
```

### Confirming Relations

Users confirm a suspect relation via `POST /api/v1/relations/{id}/confirm/`, which:

- Resets `source_version` to the source item's `current_version`
- Resets `target_version` to the target item's `current_version`
- Optionally accepts explicit version numbers or sets `version_pinned` to `true`

### Navigation Suspect Flags

The navigation endpoint (`GET /api/v1/items/{id}/navigation/`) surfaces suspect status per relation:

| Field                 | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| `is_suspect`          | `true` if either side changed since the relation was confirmed |
| `other_changed`       | `true` if the other item was edited after relation confirmed   |
| `self_changed`        | `true` if the current item was edited after relation confirmed |
| `pinned_version`      | The version of the *other* item stored on the relation         |
| `current_version`     | The *other* item's current version                             |
| `self_pinned_version` | The version of the *current* item stored on the relation       |
| `self_current_version`| The *current* item's current version                           |
| `is_version_pinned`   | `true` if the user explicitly pinned the relation to a version |

---

## Composition vs Trace Relations

Relations have a `kind` that determines their role in the data model:

| Aspect       | Composition                    | Trace                              |
|--------------|--------------------------------|------------------------------------|
| Purpose      | Defines tree hierarchy         | Defines horizontal traceability    |
| Built-in     | `is_composed_of`               | `traces_to`                        |
| Navigation   | parent / children / siblings   | left (incoming) / right (outgoing) |
| Tree view    | Shown in composition tree      | Not shown in tree                  |
| Ordering     | Uses `position` field          | No ordering                        |
| Cardinality  | An item can have at most one composition parent | An item can have many trace relations |

### Composition Relations

Composition relations form a strict tree hierarchy. The built-in `is_composed_of` relation type is the default. Key properties:

- An item's **parent** is the source of an incoming composition relation
- An item's **children** are the targets of its outgoing composition relations
- **Siblings** are other children of the same parent
- Children are ordered by the `position` field and can be reordered via the `reorder-children` endpoint
- Root items (those with no composition parent) are returned by the `roots` endpoint

### Trace Relations

Trace relations define horizontal traceability links between items. The built-in `traces_to` relation type is the default, but custom trace relation types can be created. Key properties:

- **Left panel** in the navigator shows incoming trace relations (where the current item is the target)
- **Right panel** shows outgoing trace relations (where the current item is the source)
- Trace relations participate in suspect link tracking
- Trace relations are followed by traceability matrix traversal columns

### Built-in Relation Types

Two relation types are created automatically for each vault and cannot be deleted:

| Name             | Kind          | Forward Label   | Reverse Label    |
|------------------|---------------|-----------------|------------------|
| `is_composed_of` | `composition` | is composed of  | composed in      |
| `traces_to`      | `trace`       | traces to       | traced by        |

Custom relation types of either kind can be created to model additional relationships.
