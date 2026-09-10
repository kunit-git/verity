# REST API reference

[Documentation index](../../docs/README.md) · [Data model](data-model.md) ·
[Runnable walkthrough](../../docs/examples/api_quickstart.py)

## Connection and authentication

The base URL is `https://YOUR_DOMAIN/api/v1` in production, or
`http://localhost:8000/api/v1` for local development. Paths below are relative to
that base. Use trailing slashes, `Content-Type: application/json` for JSON bodies,
and `Authorization: Bearer ACCESS_TOKEN` for authenticated endpoints.

`POST /auth/login/` accepts `{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}`
and returns `access` and `refresh`. Treat both as secrets. Access tokens last
30 minutes; refresh tokens last 7 days. `POST /auth/refresh/` accepts
`{"refresh":"REFRESH_TOKEN"}` and returns a new `access` token. Do not put tokens
in query strings or public logs. There is no server-side logout/revocation endpoint.

Select a vault before calling content APIs:

1. `GET /vaults/my/` returns the vaults the current user can access.
2. `POST /vaults/select/` with `{"vault_id":"VAULT_UUID"}` changes the active vault.
3. `GET /auth/me/` includes `active_vault`, its name/lock state, and `vault_role`.

Vault selection is stored on the account and affects other sessions using the
same account. Most content URLs do not contain a vault ID. Site admins also
select a vault for these endpoints. References in content payloads must belong
to that vault. UUID placeholders in examples must be replaced with real returned
IDs; user IDs are integers.

## Pagination and errors

Most collection endpoints return:

```json
{"count": 0, "next": null, "previous": null, "results": []}
```

Default page size is 50; follow `next` or send `?page=2`. Vault lists,
my-vault lists, member lists, and the user directory are unpaginated arrays.
Nested collections in detail responses are not necessarily paginated.

| Status | Meaning |
| --- | --- |
| 200 / 201 / 204 | Success / creation / success with no response body. |
| 202 | Registration accepted pending administrator approval. |
| 400 | Invalid fields or an invalid operation; inspect field errors or `detail`. |
| 401 | Missing, expired, or invalid authentication; inactive accounts cannot log in. |
| 403 | Missing vault/role permissions, locked content, disabled registration, or a mailbox limit. |
| 404 | Resource not found within the caller's permitted scope. |
| 409 | Setup already complete, or another explicit resource conflict. |
| 429 | Setup/application-proxy throttling. |
| 503 | Setup database unavailable or AI provider configuration unavailable. |

Validation errors may be keyed by field, nested under `sources`/`custom_fields`,
or returned under `non_field_errors`/`detail`. Do not depend on exact error text.
An SSE error is sent inside the stream after its HTTP response has begun.

## Accounts and site settings

| Methods | Path | Body or behavior | Access |
| --- | --- | --- | --- |
| GET, POST | `/auth/setup/` | GET returns `setup_required`; POST creates the first admin from username/password and optional email. POST is throttled and returns 409 once any site admin exists. | Public; provision before exposing a fresh site. |
| GET, PATCH | `/auth/settings/` | GET settings; PATCH selected site-setting fields. | GET public; PATCH site admin. |
| POST | `/auth/register/` | Username, email, password; creates a locked/inactive account and returns 202. | Public when registration enabled. |
| POST | `/auth/login/` | Username/password → JWT pair. | Public. |
| POST | `/auth/refresh/` | Refresh token → access token. | Requires a valid refresh token. |
| GET, PATCH | `/auth/me/` | Own profile; PATCH username/email. Role and active-vault fields are read-only here. | Authenticated. |
| POST | `/auth/me/password/` | `current_password`, `new_password`; 204 on success. | Authenticated. |
| GET | `/auth/users/` | Site-wide account directory; `?include_deleted=true` includes deleted-status accounts. | Site admin or admin of active vault. |
| POST | `/auth/users/create/` | Username/email/password; creates an active account. | Site admin. |
| GET, PATCH | `/auth/users/{id}/` | Account detail; PATCH `is_site_admin`. | Site admin. |
| POST | `/auth/users/{id}/password/` | `new_password`; 204. | Site admin. |
| POST | `/auth/users/{id}/lock/` | Locks/inactivates the account. | Site admin. |
| POST | `/auth/users/{id}/unlock/` | Activates a locked account. | Site admin. |
| POST | `/auth/users/{id}/delete/` | Sets deleted status and inactive; retains the account row. | Site admin. |

Passwords accepted by the registration/password serializers require at least
eight characters. Account creation does not add a vault membership. Lock/delete
endpoints reject targeting the caller's own account.

Public/non-admin settings GET returns `registration_enabled`, `mailbox_limit`,
and `ai_enabled`. Site-admin GET also returns `ai_provider_type`, `ai_api_url`,
`ai_model`, and `ai_api_key_set`; it never returns `ai_api_key`. PATCH may write
the key: omit to preserve it, send an empty string to clear it. See
[configuration](../../docs/configuration.md#settings-stored-in-the-database).

## Vaults and membership

| Methods | Path | Body or behavior | Access |
| --- | --- | --- | --- |
| GET, POST | `/vaults/` | List all vaults; create with `name`, `slug`, optional `description`. | Site admin. |
| GET, PATCH, DELETE | `/vaults/{id}/` | Detail; change name/slug/description; soft-delete. | Site admin. |
| GET | `/vaults/my/` | Accessible vaults, including `my_role` and lock status. | Authenticated. |
| POST | `/vaults/select/` | `vault_id`; selects an accessible vault. | Member or site admin. |
| POST | `/vaults/{id}/lock/` | Lock the requested vault; no body required. | Admin of requested vault or site admin. |
| POST | `/vaults/{id}/unlock/` | Unlock the requested vault. | Admin of requested vault or site admin. |
| GET, POST | `/vaults/{vault_id}/members/` | List; add with integer `user` and `role` (`viewer`, `editor`, `admin`). | Admin of requested vault or site admin. |
| GET, PATCH, DELETE | `/vaults/{vault_id}/members/{membership_id}/` | Read membership; PATCH role; remove membership. | Admin of requested vault or site admin. |
| GET | `/vaults/{vault_id}/audit-log/` | Paginated creation/member/locking events. | Admin of requested vault or site admin. |

Membership/audit access checks the vault in the URL. Membership changes are
blocked while that vault is locked. A site's administrator membership cannot be
changed through the member-detail endpoint, and removing the last admin membership
is rejected. Creating a vault does not select it automatically.

## Content permissions

Items, item types/custom fields, relation types/relations, templates, and tables
require access to the active vault. Viewers can read; editors and admins can
write only while it is unlocked. Mailbox and AI conversation operations have the
separate rules described below. These APIs do not offer anonymous vault sharing.

## Item types and custom fields

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/item-types/` | List or create with `name`, `slug`, optional description/icon. |
| GET, PUT, PATCH, DELETE | `/item-types/{id}/` | Detail/update/delete; deletion is rejected while live items use the type. |
| POST | `/item-types/{id}/custom-fields/` | Create a definition. |
| PATCH, DELETE | `/item-types/{id}/custom-fields/{field_id}/` | Update/remove a definition for that type. |
| GET, PUT, DELETE | `/item-types/{id}/template/` | Get template metadata/default/available fields; PUT `{"template":"MARKDOWN"}`; remove custom template. |

Custom field definition example:

```json
{
  "name": "Priority",
  "slug": "priority",
  "field_kind": "integer",
  "is_required": false,
  "display_order": 0,
  "options": {}
}
```

Kinds: `text`, `integer`, `decimal`, `boolean`, `date`, `choice`, `mermaid`, `table`.
Choice widgets use `options.choices`, an array of strings. Table fields use the
embedded schema below. Definition slugs must be unique within the item type.

## Items, versions, and navigation

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/items/` | List or create an item. |
| GET, PUT, PATCH, DELETE | `/items/{id}/` | Detail/update/soft-delete. |
| GET | `/items/roots/` | Paginated composition roots. |
| GET | `/items/{id}/children/` | Paginated composition children. |
| GET | `/items/{id}/ancestors/` | Ancestor ID array. |
| POST | `/items/{id}/reorder-children/` | `{"child_ids":["CHILD_UUID","ANOTHER_CHILD_UUID"]}` in desired order. |
| GET | `/items/{id}/navigation/` | Item plus parent, children, siblings, and left/right trace references. |
| GET | `/items/{id}/versions/` | Paginated stored snapshots. |
| GET | `/items/{id}/versions/{version_number}/` | Snapshot or synthesized live current-version state. |
| GET | `/items/{id}/editor-data/` | Composition subtree and templates for the document editor. |
| GET | `/items/{id}/table-field/{field_slug}/data/` | Computed embedded-table data. |
| PATCH | `/items/{id}/table-field/{field_slug}/annotate/` | Upsert an embedded-table note. |

List filters: `item_type__slug`, `status`, and `created_by`; `search` matches title
or description. Ordering supports `title`, `created_at`, `updated_at`, `status`,
and a `-` prefix for descending order.

Create example:

```json
{
  "item_type": "ITEM_TYPE_UUID",
  "title": "The system shall record sign-in events",
  "description": "Record a timestamp and account identifier.",
  "status": "draft",
  "custom_fields": {"priority": 2}
}
```

Statuses: `draft`, `active`, `in_review`, `approved`, `archived`. Pass custom values
by definition slug, not field UUID. Unknown slugs are rejected; required fields
must be supplied when validating a custom-field payload. Embedded table fields
do not use `custom_fields` values.

Updates snapshot the previous state and increment `current_version`; it is
read-only and is not an optimistic-lock token. An optional `change_summary` on an
update labels the stored snapshot. Snapshot fields include `version_number`,
title/description/status, `custom_fields_snapshot`, and actor/timestamp information.

Navigation references include `is_suspect`, `other_changed`, `self_changed`,
`pinned_version`, `current_version`, `self_pinned_version`,
`self_current_version`, and `is_version_pinned`. `left` contains incoming trace
links and `right` outgoing ones. See [version semantics](data-model.md#versions-relations-and-templates).

## Relations

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/relation-types/` | List/create a relation definition. |
| GET, PUT, PATCH, DELETE | `/relation-types/{id}/` | Detail/update/delete; built-in types cannot be deleted. |
| GET, POST | `/relations/` | List/create a link. Filter by `relation_type`, `source`, or `target`. |
| GET, PATCH, DELETE | `/relations/{id}/` | Detail/update/remove a link. |
| POST | `/relations/{id}/confirm/` | Record reviewed endpoint versions and optional pinning. |

A type has `kind` (`composition` or `trace`), `name`, `forward_label`,
`reverse_label`, optional description, and optional `source_item_type`/
`target_item_type` constraints. New vaults contain `is_composed_of` and `traces_to`.
Create a link with:

```json
{"relation_type":"RELATION_TYPE_UUID","source":"SOURCE_ITEM_UUID","target":"TARGET_ITEM_UUID"}
```

Confirm with `{}` to record both current versions and unpin, or specify existing
`source_version`, `target_version`, and `version_pinned` values. Normal link
writes cannot directly set these version fields. Keep composition data acyclic
and single-parent for tree-based UI features; this invariant is not fully enforced
by all API writes.

## Tables

| Methods | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/tables/` | List/create a standalone table. |
| GET, PUT, PATCH, DELETE | `/tables/{id}/` | Detail/update/soft-delete. |
| GET | `/tables/{id}/data/` | Evaluate and return display columns plus rows. |
| PATCH | `/tables/{id}/annotate/` | Upsert a note using `column_slug`, `row_hash`, and `value`. |

The write schema has separate named `sources` and display `columns`:

```json
{
  "name": "Requirements and tests",
  "description": "Outgoing trace links",
  "sources": [
    {"name":"requirements","kind":"seed","seed_item_type":"REQUIREMENT_TYPE_UUID"},
    {"name":"tests","kind":"traversal","relation_type":"TRACE_TYPE_UUID","direction":"outgoing"},
    {"name":"notes","kind":"annotation"}
  ],
  "columns": [
    {"heading":"Requirement","source":"requirements"},
    {"heading":"Test case","source":"tests"},
    {"heading":"Review notes","source":"notes"}
  ]
}
```

The first source must be `seed`. All source names must be unique. Display columns
reference a source by name and may order/reuse sources independently. UUID
references must belong to the active vault. Arrays are ordered and are replaced
when supplied on update. Prefer PUT with the complete definition; current PATCH
validation still requires a nonempty `sources` list even for a name-only change.

| Source kind | Required configuration |
| --- | --- |
| `seed` | `seed_item_type`; optional `seed_container` limits to its direct composition children. |
| `traversal` | `relation_type`, `direction` (`outgoing`/`incoming`). |
| `formula` | `formula`, such as `$requirements.priority * 2`. |
| `annotation` | No extra fields; uses the source name as annotation column slug. |
| `item_field` | `source_ref` plus `field_slug` to read a custom field from that source's item. |

Formulas support arithmetic and named source/custom-field references. Nonnumeric
or missing values and division by zero produce empty results. Sources are evaluated
in order; define dependencies before the formula/item-field source using them.

Data responses contain `columns` (position, heading, source, kind, optional slug)
and `rows` (one array of cells per row). Item cells have ID/title/type metadata;
missing traversal cells are null; formula cells are `{"value":NUMBER}` or null;
item-field cells have `item_field:true` and `value`. Annotation cells include
`annotation:true`, `value`, `row_hash`, and `column_slug`.

Copy the annotation cell's returned `row_hash` and `column_slug` into PATCH:

```json
{"column_slug":"notes","row_hash":"HASH_FROM_DATA_RESPONSE","value":"Reviewed"}
```

### Embedded table custom fields

An embedded table starts from its owning item and stores its schema in a custom
field definition with `field_kind:"table"`. It uses `options.columns`, not the
standalone table's `sources`/display-columns schema:

```json
{
  "name": "Linked tests",
  "slug": "linked-tests",
  "field_kind": "table",
  "options": {
    "columns": [
      {"name":"tests","label":"Test case","kind":"traversal","relation_type_id":"TRACE_TYPE_UUID","direction":"outgoing"},
      {"name":"notes","slug":"notes","label":"Notes","kind":"annotation"}
    ]
  }
}
```

The first column must be traversal. Subsequent columns may be traversal, formula,
annotation, or item_field. Annotation columns require a unique `slug`; all columns
require unique names. Retrieve data with the owning item's table-field data path,
then PATCH its annotate path using the returned column slug/hash and a value.

## Mailbox

| Methods | Path | Behavior |
| --- | --- | --- |
| GET | `/mailbox/` | Paginated documents owned by the current user, across vaults. |
| GET, DELETE | `/mailbox/{id}/` | Retrieve content or delete an owned artifact. |
| POST | `/mailbox/generate/` | `{"item_id":"ITEM_UUID"}`; generate Markdown from an item in the active vault, returning 201. |

These operations require active-vault access but not editor rights or an unlocked
vault. Use `/generate/` for creation, not a direct POST to the mailbox collection.
Generation uses a custom template if configured, otherwise a default. It traverses
a bounded composition subtree and observes the site-wide per-user mailbox limit
(zero means unlimited).

List fields include ID, filename, file size, content type, source item, vault
metadata, and creation time. Detail adds `content`. There is no separate binary
file-download endpoint; clients can save the returned Markdown text.

## AI assistant

| Methods | Path | Behavior | Access |
| --- | --- | --- | --- |
| GET | `/agent/status/` | Effective `ai_enabled` (enabled and a key exists). | Authenticated. |
| POST | `/agent/models/` | List provider models; optional overrides `ai_provider_type`, `ai_api_url`, `ai_api_key`. | Site admin. |
| GET, POST | `/agent/conversations/` | Paginated list; create with optional `title`, `context_item`. | Active-vault access; own conversations. |
| GET, DELETE | `/agent/conversations/{id}/` | Detail with messages/actions or delete conversation. | Owner in active vault. |
| POST | `/agent/conversations/{id}/chat/` | `{"message":"YOUR_MESSAGE"}` → SSE response. | Owner in active vault. |
| POST | `/agent/pending-actions/{id}/accept/` | Execute pending action once. | Owner, editor/admin, unlocked active vault. |
| POST | `/agent/pending-actions/{id}/reject/` | Mark pending action rejected. | Owner in active vault. |

Consume chat as `text/event-stream`, with blank lines separating events:

```text
event: token
data: {"content":"Response text"}

event: done
data: {}
```

Event names are `token` (`content`), `pending_action` (serialized action), `error`
(`detail`), and `done`. Handle an error followed by done. Provider adapters
currently buffer output, so the stream does not guarantee token-by-token latency.

Action types are `create_item`, `update_item`, and `create_relation`; statuses are
`pending`, `executed`, `rejected`, and `failed`. Accept may return HTTP 200 with
`status:"failed"` and an error in `result`, so inspect status rather than HTTP alone.
Already-resolved actions return 400. Failed content changes roll back. Viewers can
chat but cannot accept content edits. Use an approved provider because conversation
text and retrieved vault content leave the application when sent to it.

## Runnable example and compatibility

From the repository root, against an evaluation installation with a site-admin
account:

```bash
python3 docs/examples/api_quickstart.py --base-url http://localhost:8000/api/v1 --username admin
```

The script prompts for the password, creates a uniquely named demonstration vault,
item types, items, a trace link, and a table, then reads the table. It changes the
account's active vault and leaves the demonstration data in place. It does not
print or store tokens. Use an evaluation account/installation, not production.

There is no generated OpenAPI schema endpoint in this repository. This reference
covers intended integration workflows; model/view serializers and regression
tests define exact behavior for the checked-out revision. Validate integrations
against that revision when upgrading.
