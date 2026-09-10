# User guide

[Documentation index](README.md) · [Troubleshooting](troubleshooting.md)

## First login and first vault

1. Install Verity using the [quick start](../README.md#quick-start-with-docker).
2. On a fresh installation, complete the setup screen to create the first site
   administrator. There is no default password. Log in with that account.
3. A fresh database has no vaults. Follow the first-vault bootstrap command in
   the quick start, or load the optional synthetic examples. Reload the page and
   select the resulting vault.
4. Once a vault is selected, a site admin can create further vaults from
   **Vaults → Create Vault**. Use a readable name and a unique slug.

If you joined an existing installation, your site admin must activate your
account and a vault admin must add you to a vault. Registering does not grant
vault access. There are no email invitations, activation links, or self-service
email password resets in the current application.

## Roles and accounts

| Role | What you can do |
| --- | --- |
| Site admin | Manage site settings, user accounts, and vaults; access vault content and manage memberships. |
| Vault admin | Manage members and lock/unlock the vault you administer; edit its content. |
| Editor | Create and edit item types, fields, items, relations, templates, and tables in the selected vault. |
| Viewer | Read vault content, generate personal mailbox documents, and use personal AI conversations when enabled; cannot accept proposed edits. |

A user can be a viewer in one vault and an editor in another. The vault selector
changes the active vault for the account, including other tabs or API clients
logged in as that same user. Avoid simultaneous work in different vaults using
one account.

Site admins manage accounts under **Users**. **Add User** creates an active
account; self-registration creates a locked account awaiting approval. **Unlock**
activates a pending account. Use the registration setting on that page to close
new registrations when appropriate. Share initial credentials through your
organization's private channel and have users change their password after login.

In **Vaults**, expand a vault's members and use **Add** to select an existing
account and its role. Activation and vault membership are separate steps. The
member list is available to administrators of that vault. The account picker
uses a site-wide user directory; vault admins can see account names and emails.

## Create a small requirements project

1. Open **Item Types** and create `Requirement` with slug `requirement`.
2. Add an integer custom field named `Priority`, slug `priority`. Slugs identify
   fields in templates and API payloads; choose stable names.
3. Create a second item type named `Test Case`, slug `test-case`.
4. Use **New Item** to create a requirement such as “The system shall record an
   audit event when a user signs in.” Set its priority and save.
5. Create a test case describing how to verify that behavior.
6. Open the requirement in the navigator and add a `traces_to` relation to the
   test case. The requirement is the source; the test case is the target.

The built-in statuses are Draft, Active, In Review, Approved, and Archived. These
are item labels, not an enforced approval workflow or electronic signature.
Custom fields support text, integer, decimal, boolean, date, choice, Mermaid, and
embedded table types. Choose options and required fields before entering data;
changes to a field definition can affect existing items and templates.

## Navigate and review changes

The navigator shows composition parents/children and incoming/outgoing trace
links. `is_composed_of` points from a parent to its children; `traces_to` points
from the source to the target. Keep composition links acyclic and use one parent
per item. The UI presents a tree, but the API does not enforce a complete tree
constraint for every write.

Editing an item records its previous state in version history. Review earlier
versions and compare changes before confirming affected links. A suspect link
means at least one endpoint has changed since the link's recorded versions.
Confirming records the reviewed versions; it does not validate the engineering
content. Explicit version pins preserve the chosen reference versions.

## Build a traceability table

Open **Tables** and create a table. Define named sources first, then display
columns that refer to those sources:

1. Add a seed source for the Requirement item type.
2. Add an outgoing traversal source for `traces_to` to find linked test cases.
3. Display the requirement and test-case sources as two columns.
4. Add an annotation source for reviewer notes, if needed.

A traversal can produce several rows when one item has multiple related items.
An empty cell means no match was found. A formula such as `$requirements.priority * 2`
reads a numeric custom field from a named source. Supported operations are `+`,
`-`, `*`, `/`, parentheses, and unary minus; there are no spreadsheet functions.
Missing/nonnumeric inputs or division by zero produce an empty result.

The visual and JSON editors describe the same table. Standalone tables use
`sources` and `columns`; embedded table custom fields use `options.columns` and
start from the owning item. Their schemas differ; see the [API reference](../backend/doc/api.md#tables).

## Documents and templates

Use **Doc Templates** to configure Markdown for each item type. Placeholders use
exact names without spaces, for example:

```markdown
{{heading}} {{title}}

{{description}}

Priority: {{priority}}
Status: {{status}} · Version: {{current_version}}
```

Built-in placeholders include `heading`, `id`, `title`, `description`, `status`,
`item_type`, `current_version`, `created_by`, `created_at`, and `updated_at`.
Custom field slugs are also available. Unknown placeholders become empty text.
This is placeholder substitution, not a programming or conditional template
language. Without a custom template, generation uses the default layout.

The document editor combines an item and its composition descendants for editing.
Save pending changes before leaving. A generated Markdown document is a snapshot
of saved data and appears in **Mailbox**. Generation visits a bounded composition
subtree, rather than exporting the entire database. The current generator starts
at depth 1 and includes through depth 6.

Mailbox documents belong to the generating user and can remain visible across
vault switches. A viewer may generate documents even while a vault is locked.
Download or delete them from Mailbox; a configured mailbox limit may require
removing older documents before generating more.

## Locking and audit logs

Vault admins and site admins can lock a vault from **Vaults**. This blocks changes
to items, types, relations, tables, templates, memberships, and acceptance of AI
edits. It also applies to site admins. Unlock the vault before editing again.

Locking does not freeze the entire account or database: personal mailbox and AI
conversation operations remain available, and site-level administration has its
own permissions. The vault audit log records creation, membership changes, and
lock/unlock events. It is not a complete record of every read or edit; item version
history is separate. Neither facility is a tamper-evident compliance ledger.

## Optional AI assistant

A site admin configures the provider in **AI Settings**: enable AI, choose a
provider, enter an API key, choose a model, and optionally set a custom base URL.
Leave the URL empty to use the provider's default endpoint. Use the model-list
control to test the credentials and select an available model, then save.

The assistant can read the active vault and propose item creation, item updates,
and relations. Inspect each proposed action before accepting it. Only its
conversation owner with editor/admin rights can accept; the vault must be
unlocked. Rejection makes no content change. Conversations are private to the
owning user through the normal API.

Conversation text and retrieved vault data are sent to the configured provider.
Confirm that provider use is appropriate for your data before enabling it. API
keys are stored in the database and included in database backups. There are no
built-in provider budget limits, so monitor usage with your provider. Responses
may arrive in batches; the current provider adapters buffer model output.

## Deletion and recovery

Deleting an item or vault is not a backup strategy. Most content uses soft deletion,
but behavior varies by model and maintenance commands can permanently delete data.
There is no general undo/trash UI. Ask an operator to use a tested database backup
for recovery; see [Operations](operations.md).
