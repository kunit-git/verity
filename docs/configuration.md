# Configuration reference

[Documentation index](README.md) · [Deployment](../INSTALL.md)

## Where settings come from

Django uses `python-decouple`: process environment variables override values in
`backend/.env`, then supported development defaults apply. `manage.py`, WSGI, and
ASGI default to development settings unless `DJANGO_SETTINGS_MODULE` is set.
Production must explicitly select `verity.settings.production`.

Docker Compose reads the repository-root `.env` for `${...}` interpolation in
`docker-compose.yml`. That does not automatically pass every variable into a
container. The supplied Compose file explicitly sets development/database values;
putting production variables in a root `.env` does not convert this stack to
production. Use the [public HTTPS guide](../INSTALL.md#public-https-deployment).

`ensure_admin` and the container startup script read `os.environ` directly.
Provisioning credentials therefore must be exported to their process, not merely
written in `backend/.env`. The deployment examples use an interactive password
prompt to avoid putting a password in command history.

## Django environment variables

| Variable | Development default | Production / meaning |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | `verity.settings.development` | Set `verity.settings.production` in the service and management commands. |
| `SECRET_KEY` | Committed development-only key | Required; generate a unique random value of at least 50 characters. `django-insecure-` keys are rejected. |
| `ALLOWED_HOSTS` | Fixed localhost addresses and Docker `backend` | Required comma-separated hostnames, without schemes or ports; wildcards and empty entries are rejected. |
| `DB_NAME` | `verity` | PostgreSQL database name. |
| `DB_USER` | `verity` | Database role. The production role needs schema permissions, not superuser or createdb. |
| `DB_PASSWORD` | `verity_dev` | Explicitly required in production; use a unique password. |
| `DB_HOST` | `localhost` | Compose sets `db`; host/server deployments commonly use `127.0.0.1`. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated origins including scheme and non-default port. Use the public HTTPS origin for the documented deployment. |
| `TRUST_PROXY_HEADERS` | Not used | Production default `False`. Set `True` only with a trusted proxy that overwrites `X-Forwarded-Proto` and prevents direct access to Gunicorn. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Not used | Production default `False`; enable only if every subdomain uses HTTPS. |
| `SECURE_HSTS_PRELOAD` | Not used | Production default `False`; adds preload eligibility, but does not submit the domain to a preload list. |

Production fixes `DEBUG=False`, enables HTTPS redirects and secure session/CSRF
cookies, and sets HSTS to one year. `DEBUG`, `SECURE_SSL_REDIRECT`, and
`CSRF_TRUSTED_ORIGINS` are not environment-backed settings in this code. The
same-origin deployment in INSTALL.md does not require cross-origin session/CSRF
configuration. CORS does not replace authentication or grant vault access.

JWT access tokens last 30 minutes and refresh tokens last 7 days. These values are
in `SIMPLE_JWT` in [base.py](../backend/verity/settings/base.py), not environment
variables. Logging out clears browser tokens; there is no server-side logout or
refresh-token blacklist endpoint. Do not assume a password change revokes every
previously issued token. Lock a compromised account and follow your incident
response process.

## Docker startup controls

| Variable | Default | Effect |
| --- | --- | --- |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Username for optional provisioning. |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Email for the provisioned account. |
| `DJANGO_SUPERUSER_PASSWORD` | Empty | When explicitly supplied, startup runs `ensure_admin`; otherwise use browser setup. |
| `RECREATE_DB` | `0` | Drops and recreates the application database on startup. Destructive. |
| `RECREATE_ADMIN` | `0` | Deletes and recreates the configured admin; requires a password. Destructive and may fail for accounts referenced by protected records. |
| `LOAD_EXAMPLE` | `0` | Replaces the six example vaults and demo account; requires an existing admin. |

These flags remain in an already-created container's environment. After using a
one-time flag, recreate the backend with the flag omitted or set to `0` before any
restart. `docker compose restart` does not re-read changed environment settings.
Use `changepassword` for password recovery instead of recreating an account.

## Frontend

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Development proxy destination; Compose sets `http://backend:8000`. |
| `VITE_USE_POLLING` | False | Set `true` for file watching over Docker bind mounts. |

The browser API base is `/api/v1`, relative to the frontend origin. The production
build needs an `/api/` reverse proxy on that same origin. Do not put secrets in
`VITE_*` values. In development these two controls are read from the process
environment by `vite.config.ts`; export them before starting Vite.

## Settings stored in the database

Site admins manage these in **Users** or **AI Settings**, or through
`PATCH /api/v1/auth/settings/`:

| Field | Default | Meaning |
| --- | --- | --- |
| `registration_enabled` | `true` | Allows registration; new accounts still require approval. |
| `mailbox_limit` | `0` | Maximum stored documents per user; zero means unlimited. |
| `ai_enabled` | `false` | Allows the optional AI feature. A key must also be configured. |
| `ai_provider_type` | Empty | `openai` or `anthropic`. |
| `ai_api_url` | Empty | Optional provider base URL. Site admins control the outbound destination. |
| `ai_api_key` | Empty | Write-only API field, stored in the database; empty clears it, omission preserves it. |
| `ai_model` | Empty | Model identifier accepted by the configured provider. |

The API returns `ai_api_key_set` to site admins instead of revealing the key.
Non-admin settings responses only contain `registration_enabled`, `mailbox_limit`,
and `ai_enabled`. No `AI_API_KEY` environment variable is read by the application.
