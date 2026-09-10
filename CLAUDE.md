# Repository development guide

Public documentation starts at [README.md](README.md) and [docs/README.md](docs/README.md).
Keep those guides, rather than this file, as the source for installation commands.

## Setup and checks

The Python virtual environment is `.venv/` at the repository root. Activate it
before running commands from `backend/`. Development uses PostgreSQL 16; tests
create a separate database and need a role with database-creation permission.
`manage.py` defaults to development settings. Explicitly select production settings
for server management commands.

After backend behavior changes, add meaningful regression tests and run the full
suite with `pytest`. Factories/shared API clients live in `backend/conftest.py`;
app tests live under `backend/apps/<app>/tests/`. Cover success, permission failures,
wrong-vault access, and invalid input for changed endpoints. Run `manage.py check`
and `makemigrations --check --dry-run` when appropriate.

Frontend checks run from `frontend/`: `npm ci`, `npm run lint -- --max-warnings=0`,
and `npm run build`. Node.js 24 matches Docker and CI. Keep the lockfile updated
when dependencies change.

## Architecture

- Django REST Framework serves `/api/v1/`; JWT authenticates browser/API requests.
- Site admin is an account flag; viewer/editor/admin roles belong to vault memberships.
- Active vault is stored on the user and shared across sessions for that account.
- Most content views use `HasVaultAccess`, `ReadOnlyOrEditor`, and `VaultNotLocked`.
  Membership/audit administration must authorize the vault identified by the URL.
- Items obtain vault scope through their item type. Updates snapshot previous values
  into `ItemVersion`; relations track confirmed endpoint versions for suspect links.
- Standalone tables have named sources plus display columns; embedded table fields
  have a distinct `options.columns` schema and use the owning item as their seed.
- AI conversations/actions are private to their owner and vault. Proposed writes
  must pass the same content permissions and serializers as normal API edits.
- React uses TanStack Query for server state. Clear vault-specific caches when
  switching vaults; avoid overwriting unsaved forms on background refetches.

See [API reference](backend/doc/api.md) and [data model](backend/doc/data-model.md)
for current routes and behavior. Backend apps are accounts, vaults, items,
relations, matrices, mailbox, and agent.

## Data and configuration precautions

A fresh database has no admin or vault; use first-admin setup and the documented
first-vault bootstrap. There is no default admin password. `seed_data` only ensures
built-in relation types for existing vaults.

`populate_example` replaces six example vaults and the demo account. `purge_data`,
`seed_data --reset`, database-volume removal, and admin recreation are destructive.
Do not use them for ordinary tests or password recovery. Use isolated databases for
validation and the documented recovery procedure instead.

Do not commit `.env`, private keys, database dumps, local agent settings, or real
user data. Keep examples synthetic and deployment secrets outside public assets.
