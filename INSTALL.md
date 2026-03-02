# Verity — Production Deployment Guide

This guide covers deploying Verity on a Linux server with PostgreSQL already installed, using Nginx as a reverse proxy and Gunicorn as the WSGI application server.

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
