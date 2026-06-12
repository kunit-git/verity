# Verity — Deployment Guide

There are two ways to install Verity:

- **[Docker Compose](#install-with-docker-compose)** — the fastest path. Brings up PostgreSQL and the Django backend in containers, runs migrations, seeds data, and creates an admin user automatically. Best for local use and evaluation.
- **[Manual production deployment](#manual-production-deployment)** — Nginx + Gunicorn on a Linux host. Best for a hardened production server.

---

## Install with Docker Compose

### Prerequisites

- Docker Engine 24+ with the Compose plugin (`docker compose version`)
- The repository checked out locally

That's all — no local Python, Node, or PostgreSQL required.

### 1. Start the stack

From the repository root:

```bash
docker compose up -d --build
```

This builds and starts three containers:

| Container | Image | Purpose |
|-----------|-------|---------|
| `db` | `postgres:16-alpine` | PostgreSQL, data persisted in the `pgdata` volume |
| `backend` | built from `backend/Dockerfile` | Django API on port **8000** |
| `frontend` | built from `frontend/Dockerfile` | Vite dev server (React SPA) on port **5173**, proxying `/api` to `backend` |

On startup the backend container waits for the database to be healthy, then automatically:

1. Applies any pending migrations (`migrate`).
2. Seeds the built-in relation types (`seed_data`).
3. Provisions the admin user (`ensure_admin`).

Watch it come up:

```bash
docker compose logs -f backend
```

When you see `Starting development server at http://0.0.0.0:8000/`, the API is ready at <http://localhost:8000/api/v1/>, and the web app is served at <http://localhost:5173>.

### 2. Log in

A site admin is created on first boot. The defaults are:

| | Value |
|---|---|
| Username | `admin` |
| Password | `admin` |

Override them by setting environment variables before `up` (they are read by `docker-compose.yml`):

```bash
DJANGO_SUPERUSER_USERNAME=alice \
DJANGO_SUPERUSER_EMAIL=alice@example.com \
DJANGO_SUPERUSER_PASSWORD='a-strong-password' \
  docker compose up -d --build
```

### 3. Open the web app

The `frontend` container runs the Vite dev server and is already part of the stack — just open <http://localhost:5173> and log in. Edits to files under `frontend/src` hot-reload automatically.

Prefer to run the frontend on the host instead (e.g. to skip the container)? Stop it with `docker compose stop frontend` and run Vite directly — it proxies `/api` to `localhost:8000`:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### Triggering a database / admin reset

Two opt-in flags let you rebuild from scratch without editing any files. They default to off; set them for a single `up`:

```bash
# Drop and recreate the database, then migrate, seed, and recreate the admin
RECREATE_DB=1 docker compose up -d backend

# Recreate just the admin user (e.g. to reset a forgotten password)
RECREATE_ADMIN=1 docker compose up -d backend
```

Omit the flag on the next `up` and startup is non-destructive again (migrations only apply when pending; an existing admin is left in place).

### Loading the example data

A fresh database starts empty (just the admin and built-in relation types). To load the six demo vaults — AV System, Avionics FMS, Cardiac Pacemaker, Trading Risk Platform, NGCC Pursuit, and Meridian Analytics Deal — set `LOAD_EXAMPLE=1`:

```bash
LOAD_EXAMPLE=1 docker compose up -d backend
```

Or load them on demand into an already-running stack:

```bash
docker compose exec backend python manage.py populate_example
```

`populate_example` wipes and rebuilds only those six example vaults, so it is safe to re-run. It requires the admin account to exist first (the entrypoint creates it before this step).

### Common operations

```bash
docker compose ps                    # container status
docker compose logs -f backend       # follow backend logs
docker compose exec backend python manage.py createsuperuser   # add another user
docker compose exec db psql -U verity -d verity                # open a SQL shell
docker compose down                  # stop containers (keeps the pgdata volume)
docker compose down -v               # stop and DELETE all database data
```

### Notes on production use

The Compose setup uses `verity.settings.development` and Django's built-in `runserver` for convenience. Before exposing it publicly you should at minimum:

- Switch `DJANGO_SETTINGS_MODULE` to `verity.settings.production` and provide a real `SECRET_KEY`, `ALLOWED_HOSTS`, `DB_PASSWORD`, and `CORS_ALLOWED_ORIGINS`.
- Serve the app with a production WSGI server (Gunicorn) behind a reverse proxy with TLS, and build/serve the frontend as static files.

For a fully hardened deployment, follow the manual guide below.

---

## Manual Production Deployment

This section covers deploying Verity on a Linux server with PostgreSQL already installed, using Nginx as a reverse proxy and Gunicorn as the WSGI application server.

## Prerequisites

- Linux server (Ubuntu 22.04+ or similar)
- PostgreSQL 14+ (already installed and running)
- Nginx (already installed)
- Python 3.12+
- Node.js 20+ and npm
- A non-root system user (this guide uses `verity`)

---

## 1. Create a System User

```bash
sudo useradd --system --create-home --shell /bin/bash verity
```

---

## 2. PostgreSQL Database Setup

Connect to PostgreSQL as a superuser and create the database and role:

```sql
sudo -u postgres psql

CREATE USER verity WITH PASSWORD 'your-db-password';
CREATE DATABASE verity OWNER verity;
GRANT ALL PRIVILEGES ON DATABASE verity TO verity;
\q
```

> **Note:** Replace `your-db-password` with a strong password of your choice. You will need to enter this exact same value as `DB_PASSWORD` in the `.env` file in step 4.2.

---

## 3. Deploy the Application Code

Clone the repository or copy the source to the server:

```bash
sudo mkdir -p /opt/verity
sudo chown verity:verity /opt/verity

sudo -u verity git clone <repository-url> /opt/verity
```

---

## 4. Backend Setup

### 4.1 Python Virtual Environment

```bash
cd /opt/verity/backend
sudo -u verity python3 -m venv /opt/verity/.venv
sudo -u verity /opt/verity/.venv/bin/pip install --upgrade pip
sudo -u verity /opt/verity/.venv/bin/pip install -r requirements.txt
sudo -u verity /opt/verity/.venv/bin/pip install gunicorn
```

### 4.2 Environment Variables

Create `/opt/verity/backend/.env`:

```ini
SECRET_KEY=your-django-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com

DB_NAME=verity
DB_USER=verity
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

**`SECRET_KEY`** is Django's cryptographic signing key — it is unrelated to the database password. Generate a unique value for it:

```bash
/opt/verity/.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**`DB_PASSWORD`** must be the same password you set for the `verity` PostgreSQL user in step 2.

### 4.3 Run Migrations and Seed Data

```bash
cd /opt/verity/backend

DJANGO_SETTINGS_MODULE=verity.settings.production \
  /opt/verity/.venv/bin/python manage.py migrate

DJANGO_SETTINGS_MODULE=verity.settings.production \
  /opt/verity/.venv/bin/python manage.py seed_data

DJANGO_SETTINGS_MODULE=verity.settings.production \
  /opt/verity/.venv/bin/python manage.py collectstatic --noinput
```

`seed_data` creates the built-in relation types (`is_composed_of`, `traces_to`). To load example data instead, replace `seed_data` with `populate_example` (this also creates demo users).

### 4.4 Create an Admin User (if not using example data)

```bash
DJANGO_SETTINGS_MODULE=verity.settings.production \
  /opt/verity/.venv/bin/python manage.py createsuperuser
```

---

## 5. Frontend Build

```bash
cd /opt/verity/frontend
npm ci
npm run build
```

This produces a static bundle in `/opt/verity/frontend/dist/`.

---

## 6. Gunicorn — WSGI Application Server

### 6.1 Systemd Service

Create `/etc/systemd/system/verity.service`:

```ini
[Unit]
Description=Verity Django Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=verity
Group=verity
WorkingDirectory=/opt/verity/backend
Environment="DJANGO_SETTINGS_MODULE=verity.settings.production"
ExecStart=/opt/verity/.venv/bin/gunicorn verity.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile /var/log/verity/access.log \
    --error-logfile /var/log/verity/error.log
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 6.2 Create Log Directory and Start

```bash
sudo mkdir -p /var/log/verity
sudo chown verity:verity /var/log/verity

sudo systemctl daemon-reload
sudo systemctl enable verity
sudo systemctl start verity
```

Verify it is running:

```bash
sudo systemctl status verity
curl -s http://127.0.0.1:8000/api/v1/items/ -H "Content-Type: application/json"
```

---

## 7. Nginx — Reverse Proxy

Create `/etc/nginx/sites-available/verity`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend — static SPA
    root /opt/verity/frontend/dist;
    index index.html;

    # API and admin — proxy to Gunicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django static files (admin CSS/JS)
    location /static/ {
        alias /opt/verity/backend/staticfiles/;
    }

    # SPA fallback — all other routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Enable the site and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/verity /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. TLS with Let's Encrypt (recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

Certbot will update the Nginx config to redirect HTTP to HTTPS and install the certificate. After enabling TLS, update your `.env`:

```ini
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

Then restart Gunicorn:

```bash
sudo systemctl restart verity
```

---

## 9. Tuning

### Gunicorn Workers

A common formula is `(2 x CPU cores) + 1`. For a 2-core server:

```
--workers 5
```

### PostgreSQL

Ensure `pg_hba.conf` allows the `verity` user to connect from `localhost` via `md5` or `scram-sha-256`.

### Log Rotation

Create `/etc/logrotate.d/verity`:

```
/var/log/verity/*.log {
    weekly
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        systemctl reload verity
    endscript
}
```

---

## 10. Updating

```bash
cd /opt/verity

# Pull latest code
sudo -u verity git pull

# Backend
cd backend
sudo -u verity /opt/verity/.venv/bin/pip install -r requirements.txt
DJANGO_SETTINGS_MODULE=verity.settings.production \
  sudo -u verity /opt/verity/.venv/bin/python manage.py migrate
DJANGO_SETTINGS_MODULE=verity.settings.production \
  sudo -u verity /opt/verity/.venv/bin/python manage.py collectstatic --noinput

# Frontend
cd ../frontend
sudo -u verity npm ci
sudo -u verity npm run build

# Restart
sudo systemctl restart verity
```

---

## Quick Reference

| Component | Location |
|-----------|----------|
| Backend code | `/opt/verity/backend/` |
| Frontend build | `/opt/verity/frontend/dist/` |
| Virtual environment | `/opt/verity/.venv/` |
| Environment config | `/opt/verity/backend/.env` |
| Systemd service | `/etc/systemd/system/verity.service` |
| Nginx site config | `/etc/nginx/sites-available/verity` |
| Application logs | `/var/log/verity/` |
| Django admin | `https://yourdomain.com/admin/` |
