# Data model and access boundaries

[Documentation index](../../docs/README.md) · [API reference](api.md)

## Core records

| Record | Scope and purpose |
| --- | --- |
| `User` | Site-wide account; `is_site_admin`, `account_status`, `is_active`, and the account's `active_vault`. |
| `SiteSettings` | Singleton for registration, mailbox limits, and optional AI configuration/credentials. |
| `Vault` / `VaultMembership` | Workspace and per-user viewer/editor/admin membership. |
| `ItemType` / `CustomFieldDefinition` | Vault-specific item schema and named custom fields. |
| `Item` / `CustomFieldValue` | Current item state; its vault follows `item_type.vault`. Custom values are JSON values in separate rows. |
| `ItemVersion` | Pre-update item snapshot and version number. |
| `RelationType` / `ItemRelation` | Vault-specific directional relation definitions and links between items. |
| `DocumentTemplate` | Markdown template for an item type. |
| `Matrix` / `MatrixSource` / `MatrixDisplayColumn` | A standalone traceability table, its named data sources, and displayed columns. |
| `MatrixAnnotation` / `ItemTableAnnotation` | Notes keyed by table/field, annotation source, and row hash. |
| `MailboxArtifact` | A generated document owned by a user, with source-vault/item metadata. |
| `Conversation` / `Message` / `PendingAction` | User-and-vault-scoped AI history and proposed changes. |
| `VaultAuditLog` | Vault creation, member changes, and locking events. |

Most content IDs are UUIDs; user IDs are integers. Timestamps use Django's
configured UTC timezone. See the [model source](../apps/) and migrations for field
constraints and exact defaults.

## Permissions and roles

Site administration is a global flag, separate from Django's `is_staff` and
`is_superuser`. The standard Django `createsuperuser` command does not set the
Verity flag; first-admin setup and `ensure_admin` do.

| Access | Scope |
| --- | --- |
| Site admin | User/site configuration, vault creation/deletion, and content access in any selected vault. |
| Vault admin | Member administration and audit access for the requested vault, lock/unlock, and content editing. |
| Editor | Read/write access to content, schema, templates, and tables in an active member vault. |
| Viewer | Content reads, personal document generation, and personal AI conversations; no content edits or action acceptance. |

The normal content permission stack is `HasVaultAccess`, `ReadOnlyOrEditor`, and
`VaultNotLocked`. Site admins bypass membership checks, but still select an active
vault and obey content locking. Membership/audit endpoints authorize the vault ID
in the URL, independently of which vault is currently active.

`active_vault` is stored on the user, not in a JWT or tab session. Switching it
affects future requests from every client using that account. Clients should clear
vault-specific caches after switching. Most content endpoints obtain scope from
this field; passing a different vault ID in the payload does not change it.

The user directory is site-wide and readable by site admins or an admin in their
active vault, to support selecting accounts for memberships. AI conversations and
actions additionally require ownership. Mailbox queries are scoped to the user,
not filtered to only their active vault; access still requires an active vault.

## Locking and audit coverage

A vault stores `is_locked`, `locked_at`, and `locked_by`. Locking blocks normal
item/type/relation/table/template writes, member changes, and AI action acceptance,
including for site admins. It does not block all database writes: mailbox
operations, personal conversations, and action rejection use different permissions.
Site-level administration is also separate.

The audit log records `vault_created`, `member_added`, `member_removed`,
`member_role_changed`, `vault_locked`, and `vault_unlocked`. It does not record
every API request or every item edit. Item versions provide a separate history;
there is no tamper-evident audit or electronic-signature mechanism.

## Soft deletion and recovery

Models derived from `SoftDeleteModel` store `is_deleted` and `deleted_at`.
Their `objects` manager excludes deleted rows; `all_objects` includes them.
Model deletion can invoke model-specific soft cascades, while queryset deletion
and maintenance `hard_delete()` calls have different behavior.

Examples from current model hooks:

- Item deletion marks its custom values, item versions, relations, and embedded
  table annotations deleted.
- Type deletion marks its definitions/templates; the API refuses to delete a type
  with live items.
- Vault deletion marks the vault and memberships deleted. It does **not** recursively
  erase all contained item data.
- User removal through the account API sets `account_status=deleted` and
  `is_active=False`; it does not use `SoftDeleteModel`.
- `SiteSettings` and `VaultAuditLog` are ordinary Django models.

Do not interpret soft deletion as guaranteed retention or recovery. Protected
foreign keys, explicit hard-delete methods, and destructive maintenance commands
also exist. There is no general public restore endpoint, and restoring a parent
row is not automatically a complete cascade restore. Use tested database backups
for operational recovery; see [Operations](../../docs/operations.md).

## Versions, relations, and templates

Items start at `current_version=1`. Updates through `ItemSerializer` snapshot the
pre-update title, description, status, and custom values into `ItemVersion`, then
increment the live version. The version-detail endpoint can synthesize the current
version from live data. These snapshots are not immutable backups of every related
schema/template/link, and there is no general optimistic-concurrency contract in
the item API.

An `ItemRelation` records `source_version` and `target_version` when created or
confirmed. A link becomes suspect when a recorded endpoint version is behind the
current item version. Confirming can select existing version numbers and set
`version_pinned`. This records a reference decision; it does not approve item
content automatically.

Composition relations use `position` to order parent→child links. Trace relations
provide source→target navigation and table traversal. The UI expects an acyclic
composition tree with one parent per item, but the API does not enforce that full
invariant for every operation. Keep the data tree-shaped when using the tree and
document editors; traversal code uses visited sets/depth bounds where implemented.

New vaults automatically receive:

| Name | Kind | Forward label | Reverse label |
| --- | --- | --- | --- |
| `is_composed_of` | `composition` | is composed of | is part of |
| `traces_to` | `trace` | traces to | is traced from |

Built-in relation types cannot be deleted through the relation-type endpoint.
Labels and existing imported data can differ. `seed_data` ensures these types in
existing vaults; it does not create a first user or first vault.

Templates substitute `{{placeholder}}` values into Markdown and default to a
built-in layout when no custom template is configured. Generated mailbox documents
are snapshots, not live views. The generator's current depth range is 1–6.

## Tables and AI data

Standalone tables keep source definitions separate from display columns. Sources
can seed, traverse, calculate, annotate, or select a custom field. A display column
references a source by name. Embedded table fields have an implicit seed (the
owning item) and a distinct `options.columns` schema. Changing traversal identities
can change row hashes, so old annotations may no longer appear on newly shaped rows.

AI conversation/message data and provider keys live in PostgreSQL. Accepted actions
use the normal content serializers, require the conversation owner to have edit
access, and are resolved under a database lock to prevent duplicate acceptance.
A failed action rolls back its content changes and records a failed status.
