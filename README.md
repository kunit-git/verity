# Verity

Verity is a self-hosted systems engineering application for requirements, risks,
test cases, and traceability. A Django API and React frontend store data in
PostgreSQL.

[Documentation](docs/README.md) · [Public deployment](INSTALL.md#public-https-deployment)

## Features

- Separate vaults with viewer, editor, and administrator roles, locking, and audit logs
- Configurable item types, custom fields, version history, and document templates
- Composition trees and directional trace links, including suspect-link tracking
- Traceability tables with traversal, formula, annotation, and item-field sources
- Generated Markdown documents delivered to a personal mailbox
- Optional AI assistant with proposed edits that require user acceptance

## Quick start with Docker

Install Docker with the Compose plugin, check out this repository, and run from
its root:

```bash
docker compose up -d --build
```

Open **http://localhost:5173** and create the first administrator using the setup
screen. There is no default administrator password. A fresh database has no vaults;
bootstrap the first one after setup with:

```bash
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.vaults.models import Vault; Vault.objects.get_or_create(slug='workspace', defaults={'name': 'Workspace', 'created_by': get_user_model().objects.filter(is_site_admin=True).first()})"
```

Reload the browser and select **Workspace**. You can now create more vaults from
**Vaults**, define item types, and add team accounts. Registered accounts require
administrator approval and vault membership before they can work. Follow the
[step-by-step user guide](docs/user-guide.md) for a small requirements project.

The development stack exposes PostgreSQL on port 5432, Django on 8000, and Vite on
5173, all bound to localhost. It uses a public development database password and
Django development settings. For a public server, follow [INSTALL.md](INSTALL.md).
Complete first-admin setup before exposing an installation to other users.
A public HTTPS installation still requires login and vault permissions; the app
has no anonymous project-sharing mode.

```bash
docker compose logs -f backend
docker compose down                 # stop; preserve the database volume
```

After creating an administrator, you can load synthetic examples:

```bash
docker compose exec backend python manage.py populate_example
```

This replaces the six example vaults and the `demo` account, including edits made
there. Use it only in an evaluation installation. The demo login is `demo` /
`DEMOdemo123!`.

## Local development

Use Python 3.12 or newer (Docker and CI use 3.14), Node.js 24, npm, and PostgreSQL
16. Start only the database if running the application on your host:

```bash
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and complete setup. Create the first vault using the
bootstrap command above, replacing `docker compose exec backend python` with
`python` from `backend/` in the activated virtual environment. Then reload and
select Workspace. Vite proxies `/api` to `127.0.0.1:8000`.
The backend reads `backend/.env` for host development; Compose supplies its own
environment. Keep real credentials out of version control.

## Checks

With the virtual environment active and PostgreSQL running:

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
pytest -q
```

Tests create and destroy a separate `test_verity` database. The database role must
have permission to create databases. Override `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER`, and `DB_PASSWORD` when using a different local database.

```bash
# From the repository root in a separate terminal
cd frontend
npm run lint -- --max-warnings=0
npm run build
npm audit
```

GitHub Actions runs backend tests, migration checks, frontend lint/build, and
Python/npm dependency audits. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution
instructions and [SECURITY.md](SECURITY.md) for security reporting and deployment
boundaries.

## Project layout

| Path | Purpose |
| --- | --- |
| `backend/apps/accounts` | Authentication, site settings, and user management |
| `backend/apps/vaults` | Vault access, locking, membership, and audit logs |
| `backend/apps/items` | Items, custom fields, versions, and templates |
| `backend/apps/relations` | Composition, traceability, and graph navigation |
| `backend/apps/matrices` | Table sources, formulas, and traversal |
| `backend/apps/mailbox` | Generated documents |
| `backend/apps/agent` | Optional AI conversations and proposed actions |
| `frontend/src` | React UI and typed API clients |

## Documentation and help

Start with the [documentation index](docs/README.md). It covers first-use workflows,
roles, configuration, public HTTPS deployment, backups/restores, account recovery,
and troubleshooting. The [API reference](backend/doc/api.md) includes a
[runnable integration example](docs/examples/api_quickstart.py); the
[data model guide](backend/doc/data-model.md) explains access and deletion behavior.

For non-security bugs, use the repository's issue tracker with a reproducible
example and redacted logs. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md) for the appropriate reporting channel. There is no
published support SLA or guaranteed capacity; test with representative data before
relying on an installation.

## License

A project license has not yet been selected. Public visibility alone does not grant
an open-source license. Third-party dependencies retain their own licenses.
