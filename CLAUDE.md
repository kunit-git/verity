# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

### Full stack via Docker

`docker compose up` builds and runs three containers: `db` (PostgreSQL),
`backend` (Django on port 8000), and `frontend` (Vite dev server on port 5173,
proxying `/api` to the backend). The backend entrypoint waits for the DB,
applies migrations, seeds built-in relation types, and provisions the admin
user (`admin` / `admin` by default — override with `DJANGO_SUPERUSER_*`).
The web app is then available at <http://localhost:5173>.

```bash
docker compose up -d --build         # start db + backend
docker compose logs -f backend       # follow startup / migration output
```

To trigger a destructive reset, set a flag for a single `up` (it defaults
to off):
```bash
RECREATE_DB=1 docker compose up -d backend       # drop + recreate DB, migrate, seed, admin
RECREATE_ADMIN=1 docker compose up -d backend     # delete + recreate just the admin user
LOAD_EXAMPLE=1 docker compose up -d backend       # also load the six demo vaults (populate_example)
```

The admin command is also available standalone: `python manage.py ensure_admin [--recreate]`.

### DB-only (running the backend on the host)

To run just PostgreSQL in Docker and the backend natively:
```bash
docker compose up -d db
```

**Backend** (Django, runs on port 8000):
```bash
source .venv/bin/activate
cd backend
DJANGO_SETTINGS_MODULE=verity.settings.development python manage.py runserver
```

**Frontend** (Vite + React, runs on port 5173):
```bash
cd frontend
npm run dev
```

The Vite dev server proxies all `/api` requests to `localhost:8000`, so the frontend always calls `/api/v1/...` with no CORS concerns in dev.

## Common Commands

```bash
# Backend — run from backend/ with venv active
python manage.py migrate
python manage.py seed_data           # seeds built-in relation types; run after every migration reset
python manage.py populate_example    # wipes all data and loads AV system demo data
python manage.py createsuperuser

# Frontend — run from frontend/
npm run lint
npm run build
```

The Python venv is at `.venv/` in the project root (not inside `backend/`). Always activate it from the root: `source .venv/bin/activate`.

`DJANGO_SETTINGS_MODULE` defaults to `verity.settings.development` when running `manage.py` locally. For production use `verity.settings.production`.

## Testing

The backend has a pytest test suite. When adding new functionality or modifying existing endpoints, always write tests for the new/changed behavior. After completing any backend change, run the full test suite to confirm nothing is broken.

```bash
# Run from backend/ with venv active
pytest                              # all tests
pytest -x                           # stop on first failure
pytest apps/accounts/tests/ -v      # single app
pytest apps/items/tests/test_item_crud.py::TestItemCreate -v  # single class
```

### Writing tests

- Tests live in `apps/<app>/tests/test_*.py`. Add tests to the relevant app's test directory.
- Use the factories and fixtures defined in `backend/conftest.py` (`UserFactory`, `VaultFactory`, `ItemTypeFactory`, `ItemFactory`, etc.) to set up test data.
- Use the shared fixtures `editor_client`, `viewer_client`, and `site_admin_client` for authenticated API calls. These are pre-configured with JWT tokens and vault access.
- Every new endpoint needs tests for: success case, permission checks (viewer vs editor vs admin), and input validation (400 on bad data).
- Run `pytest` after every backend change to verify all tests pass before considering the work done.

## Architecture

### Backend (`backend/`)

Django REST Framework API under `api/v1/`. Five Django apps:

- **`apps/accounts`** — Custom `User` model with roles (`viewer`, `editor`, `admin`). Default role is `viewer`. JWT auth via simplejwt. `SiteSettings` singleton controls whether registration is enabled. `ReadOnlyOrEditor` is the standard permission class: viewers get GET, editors/admins get write access.
- **`apps/items`** — `ItemType`, `Item`, `ItemVersion`, `CustomFieldDefinition`, `CustomFieldValue`. Every `PATCH` to an item snapshots the current state into `ItemVersion` and increments `current_version`. Custom fields are stored as key/value rows (not JSON on the item).
- **`apps/relations`** — `RelationType` (kind: `composition` or `trace`) and `ItemRelation`. Two built-in relation types (`is_composed_of`, `traces_to`) are indestructible. The `ItemNavigationView` computes the spatial navigator context (parent, children, siblings, left, right) and suspect-link flags.
- **`apps/matrices`** — Traceability matrix tables: configurable columns that follow a relation type through the graph.
- **`apps/mailbox`** — Per-user generated Markdown documents stored as `MailboxArtifact` records.

### Suspect Link Tracking

When a relation is created, `source_version` and `target_version` are set to each item's `current_version` at that moment (set in `ItemRelation.save()` on `_state.adding`). A relation becomes **suspect** when either stored version falls behind the linked item's current version — meaning one side was edited after the relation was confirmed. The `ItemNavigationView` surfaces `is_suspect`, `other_changed`, and `self_changed` flags. Users confirm a relation via `POST /relations/{id}/confirm/`, which resets both versions to current.

**Important:** `ItemRelation.source_version`/`target_version` must never be left NULL for suspect tracking to work. The model's `save()` auto-sets them, but if relations are created via `bulk_create` or raw SQL (bypassing `save()`), a backfill step is needed.

### Frontend (`frontend/src/`)

React 19 + TypeScript SPA.

- **`api/`** — Thin typed wrappers over axios. The axios instance in `client.ts` handles JWT refresh automatically on 401.
- **`pages/ItemNavigator.tsx`** — The main view. Renders a three-column layout: incoming trace relations (left), item detail (center), outgoing trace relations (right). Composition-kind relations define the tree hierarchy and do not appear in the left/right panels. Suspect relations show an amber warning with a Confirm button.
- **`components/CompositionTree.tsx`** — Persistent sidebar panel showing the `is_composed_of` hierarchy with lazy-loaded children.
- **State management** — TanStack Query for all server state. Query keys follow the pattern `["item", id]`, `["navigation", id]`, `["tree"]`, etc.

### Data Model Key Points

- `Item.current_version` starts at 1 and increments on every PATCH. `ItemVersion` snapshots are created *before* applying the update (so version N snapshot holds the state that existed at version N before the change).
- `RelationType.kind` is either `composition` or `trace`. Composition relations define the tree; trace relations define the horizontal navigation axis.
- `ItemRelation` has a `position` field for ordering children under a parent (used by `reorder-children` endpoint).
- The `populate_example` management command fully wipes all user data and items before seeding — do not run in production.
