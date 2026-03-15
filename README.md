# Verity

A systems engineering item management platform for organizing and tracing requirements, risks, test cases, failure modes, and failure causes.

## Features

- **Typed items** — predefined types (Requirement, Risk, Test Case, Failure Mode, Failure Cause) with type-specific custom attributes
- **User-defined types** — create new item types and define their attributes directly in the UI
- **Directional relations** — two built-in relation types (is_composed_of, traces_to) plus user-defined types, with forward and reverse labels
- **Composition tree** — persistent tree panel showing the is_composed_of hierarchy with lazy-loaded, paginated children
- **Spatial navigator** — browse items with left/right panels for incoming/outgoing trace relations
  - **Sibling bar** — scroll through items at the same level
  - **Keyboard arrows** — navigate without touching the mouse
- **Full user management** — registration, JWT login, role-based access (viewer / editor / admin)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6, Django REST Framework, simplejwt |
| Database | PostgreSQL 16 |
| Frontend | React 19, TypeScript, Vite |
| Styling | Tailwind CSS 4 |
| State | TanStack Query 5 |

---

## Prerequisites

- Python 3.11+
- Node 18+ and npm
- Docker and Docker Compose (for PostgreSQL)

---

## Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd verity
```

### 2. Start the database

```bash
docker-compose up -d
```

This starts a PostgreSQL 16 container on port `5432` with:
- Database: `verity`
- User: `verity`
- Password: `verity_dev`

### 3. Set up the Python backend

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Enter the backend directory
cd backend

# Apply database migrations
python manage.py migrate

# Load seed data (item types, custom fields, relation types)
python manage.py seed_data
```

### 4. Set up the frontend

```bash
# From the project root
cd frontend
npm install
```

---

## Running

Open two terminals.

**Terminal 1 — Backend:**
```bash
source .venv/bin/activate
cd backend
python manage.py runserver
```
API available at `http://localhost:8000`

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```
App available at `http://localhost:5173`

The frontend dev server proxies all `/api` requests to the Django backend automatically, so no CORS configuration is needed during development.

---

## First Use

1. Open `http://localhost:5173`
2. Click **Register** and create an account
3. Log in — you land on the Dashboard
4. Click **New Item** to create your first item
5. Open an item to enter the **Navigator** view and start linking items

---

## Environment Variables

The backend reads configuration from environment variables (via `python-decouple`). For local development the defaults work out of the box. To override, create `backend/.env`:

```env
SECRET_KEY=your-secret-key-here
DB_NAME=verity
DB_USER=verity
DB_PASSWORD=verity_dev
DB_HOST=localhost
DB_PORT=5432
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

For production, set `DJANGO_SETTINGS_MODULE=verity.settings.production` and add `ALLOWED_HOSTS` to the environment.

---

## Project Structure

```
verity/
├── docker-compose.yml          # PostgreSQL service
├── .venv/                      # Python virtual environment (not committed)
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── verity/
│   │   ├── settings/
│   │   │   ├── base.py         # Shared settings
│   │   │   ├── development.py  # DEBUG=True, ALLOWED_HOSTS=*
│   │   │   └── production.py   # DEBUG=False
│   │   └── urls.py             # Root URL config
│   └── apps/
│       ├── accounts/           # User model, JWT auth endpoints
│       ├── items/              # ItemType, Item, CustomField models + API
│       │   └── management/commands/seed_data.py
│       └── relations/          # RelationType, ItemRelation, navigation API
│
└── frontend/
    ├── vite.config.ts          # Dev proxy: /api → localhost:8000
    └── src/
        ├── api/                # Typed API client (axios + JWT refresh)
        ├── auth/               # AuthContext, ProtectedRoute
        ├── components/         # Layout, sidebar
        ├── pages/
        │   ├── ItemNavigator   # Core spatial navigation view
        │   ├── ItemTypeManager # Create/edit item types and attributes
        │   └── RelationTypeManager
        └── types/              # TypeScript interfaces
```

---

## API Overview

Base URL: `http://localhost:8000/api/v1/`

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register/` | Create account |
| POST | `/auth/login/` | Get JWT tokens |
| POST | `/auth/refresh/` | Refresh access token |
| GET | `/auth/me/` | Current user |
| GET | `/item-types/` | List item types (includes custom fields) |
| POST | `/item-types/` | Create item type |
| POST | `/item-types/{id}/custom-fields/` | Add attribute to a type |
| GET | `/items/` | List items (filter: `item_type__slug`, `status`, `search`) |
| POST | `/items/` | Create item |
| GET | `/items/{id}/` | Item detail |
| PATCH | `/items/{id}/` | Update item |
| GET | `/items/{id}/navigation/` | Parent, children, siblings, left, right |
| GET | `/relation-types/` | List relation types |
| POST | `/relation-types/` | Create relation type |
| GET | `/relations/` | List relations |
| POST | `/relations/` | Create relation |
| DELETE | `/relations/{id}/` | Delete relation |

Custom fields are passed inline as a flat dict:
```json
{
  "title": "System shall handle 1000 concurrent users",
  "item_type": "<uuid>",
  "status": "draft",
  "custom_fields": {
    "priority": "High",
    "verification-method": "Test"
  }
}
```

---

## Running Tests

Tests use pytest with a dedicated test settings module. PostgreSQL must be running (the test runner creates and destroys a temporary database automatically).

```bash
# Ensure PostgreSQL is running
docker-compose up -d

# Activate the venv from the project root
source .venv/bin/activate

# Install dependencies (includes test deps)
pip install -r backend/requirements.txt

# Run all tests
cd backend
pytest

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Run a specific app's tests
pytest apps/accounts/tests/ -v
pytest apps/vaults/tests/ -v
pytest apps/items/tests/ -v
pytest apps/relations/tests/ -v
pytest apps/matrices/tests/ -v
pytest apps/mailbox/tests/ -v

# Run a specific test file
pytest apps/matrices/tests/test_formula.py -v

# Run a specific test class or function
pytest apps/accounts/tests/test_auth.py::TestLogin -v
pytest apps/accounts/tests/test_auth.py::TestLogin::test_valid_login -v

# Run with coverage report
pip install pytest-cov
pytest --cov=apps --cov-report=term-missing
```

### Test Structure

```
backend/
  conftest.py           # Factories (factory-boy) & shared fixtures
  pytest.ini            # Pytest configuration
  apps/
    accounts/tests/     # Auth, registration, user management
    vaults/tests/       # Vault CRUD, locking, members, audit log
    items/tests/        # Item types, items, versions, custom fields, templates, tree
    relations/tests/    # Relation types, relations, suspect links, navigation
    matrices/tests/     # Matrix CRUD, data traversal, formula evaluation
    mailbox/tests/      # Mailbox artifacts, document generation
```

---

## Navigation Model

The **ItemNavigator** implements a spatial metaphor for traversing the item graph:

```
                  [ Parent (Up) ]
                        |
[ Incoming (Left) ] — [ Current Item ] — [ Outgoing (Right) ]
                        |
                  [ Children (Down) ]
                  [ Sibling bar ←→ ]
```

- **Composition** (`is_composed_of`) defines the tree hierarchy. A parent is composed of its children. Shown in the persistent composition tree panel.
- **Traceability** (`traces_to`) and user-defined relations populate the horizontal axis — incoming on the left, outgoing on the right.
- Both `is_composed_of` and `traces_to` are built-in and cannot be deleted.
- Keyboard left/right arrow keys navigate relations without a mouse.
