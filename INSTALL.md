# Installation and public HTTPS deployment

[Documentation index](docs/README.md) · [Configuration](docs/configuration.md) ·
[Operations](docs/operations.md) · [Troubleshooting](docs/troubleshooting.md)

Use Docker Compose for local evaluation/development. For a publicly reachable app,
use the HTTPS deployment below. Public network access still requires a Verity
login and vault permissions; it does not make project data anonymously readable.

## Local installation with Docker Compose

Install Docker with the Compose plugin and check out the repository. From its root:

```bash
docker compose up -d --build
docker compose logs -f backend
```

The services are PostgreSQL 16, Django's development server, and Vite. They bind
to localhost at ports 5432, 8000, and 5173 respectively. The backend migrates and
seeds built-in relation types for existing vaults. There is no automatic default
administrator password or vault on a fresh database.

Open **http://localhost:5173**, complete first-admin setup, and follow the
[first-vault instructions](README.md#quick-start-with-docker). After selecting a
vault, follow the [user guide](docs/user-guide.md).

```bash
docker compose ps
docker compose logs --tail=100 backend frontend
docker compose down                 # preserves the database volume
```

For unattended evaluation, explicitly export `DJANGO_SUPERUSER_PASSWORD` and
optionally `DJANGO_SUPERUSER_USERNAME`/`DJANGO_SUPERUSER_EMAIL` before `up`.
An existing admin keeps its password. Existing non-admin users are never promoted
by provisioning. Do not use the destructive recreate flags for password recovery;
use [Operations](docs/operations.md#account-recovery).

To load synthetic examples after creating an admin:

```bash
docker compose exec backend python manage.py populate_example
```

This replaces the six example vaults and the `demo` account, including edits
there. Use only in an evaluation database. The demo login is `demo` /
`DEMOdemo123!`. See [startup controls](docs/configuration.md#docker-startup-controls)
for the exact behavior of reset and example flags.

## Public HTTPS deployment

This reference layout targets a Linux host with systemd and Ubuntu-style Nginx
configuration paths (for example Ubuntu 24.04). It uses one HTTPS origin for the
SPA, API, and Django admin, a loopback-only Gunicorn process, and local PostgreSQL.
It does not use the development Compose containers in production.

### 1. Prepare the host and domain

Required tools: Git, Python 3.12+ with venv support, Node.js 24/npm, PostgreSQL 16,
Nginx, Certbot, and rsync. Install Node.js 24 using the
[official installation instructions](https://nodejs.org/en/download), then verify
`node --version`. Do not assume the OS's default Node package meets this version.

For the other packages on Ubuntu 24.04:

```bash
sudo apt update
sudo apt install git python3-venv python3-pip postgresql nginx certbot rsync
```

Point the domain's DNS A record to this host. Configure an AAAA record only if IPv6
is also routed and configured. The example Nginx files listen on IPv4; add IPv6
listeners when needed. Permit administrative SSH access and public ports 80/443
through your host/cloud firewall. Keep PostgreSQL 5432, Gunicorn 8000, and the Vite
port closed to public traffic. Port 80 will initially serve certificate challenges
only; application access is enabled after administrator setup and TLS.

Replace `verity.example.com` throughout the example files with your domain and
`REPOSITORY_URL` below with the repository's actual clone URL. No production
hostname is embedded in the application.

### 2. Install code and database

```bash
sudo useradd --system --home-dir /opt/verity --shell /usr/sbin/nologin verity
sudo install -d -o verity -g verity /opt/verity
sudo -u verity git clone REPOSITORY_URL /opt/verity
sudo -u verity python3 -m venv /opt/verity/.venv
sudo -u verity /opt/verity/.venv/bin/pip install -r /opt/verity/backend/requirements.txt
sudo -u verity /opt/verity/.venv/bin/pip install gunicorn
```

Create a database role with a unique password at the prompt, then its database:

```bash
sudo -u postgres createuser --pwprompt verity
sudo -u postgres createdb --owner=verity verity
```

The production database role does not need superuser or database-creation rights.
For tests use a separate database role/environment with createdb permission.

### 3. Configure Django

Create `/opt/verity/backend/.env`, owned by `verity` with mode `600`:

```bash
sudo install -o verity -g verity -m 600 /dev/null /opt/verity/backend/.env
sudoedit /opt/verity/backend/.env
```

Enter the following, replacing the two placeholders and domain:

```ini
SECRET_KEY=REPLACE_WITH_A_GENERATED_RANDOM_KEY
ALLOWED_HOSTS=verity.example.com
CORS_ALLOWED_ORIGINS=https://verity.example.com
TRUST_PROXY_HEADERS=True
DB_NAME=verity
DB_USER=verity
DB_PASSWORD=REPLACE_WITH_THE_DATABASE_ROLE_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432
```

Generate the signing key with:

```bash
/opt/verity/.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Copy the result into the protected `.env`. This file is for decouple, not a shell
script; do not `source` it. Keep the file out of the public static directories and
back it up securely. Production rejects short/development signing keys and
wildcard/empty allowed hosts. See the [full reference](docs/configuration.md).

The proxy-trust setting is appropriate here because Nginx overwrites forwarded
headers and Gunicorn is only reachable on loopback. Adapt that trust boundary if
adding a CDN or load balancer. Production uses HTTPS redirects, secure cookies,
and HSTS; it will not work correctly over plain public HTTP. These choices follow
the [Django deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).

### 4. Initialize data before exposing the app

```bash
cd /opt/verity/backend
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py migrate
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py seed_data
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py collectstatic --noinput
```

Create a site admin using a password prompt (the password is not placed in shell
history). Choose an appropriate username/email in this command:

```bash
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py shell -c "from getpass import getpass; from django.core.management import call_command; call_command('ensure_admin', username='admin', email='admin@example.com', password=getpass('New admin password: '))"
```

Django's plain `createsuperuser` command does not set Verity's `is_site_admin` flag;
use the provisioning command above. It does not reset an existing admin password.

On a fresh installation, create the initial vault once (adjust the username if
changed above):

```bash
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; from apps.vaults.models import Vault; Vault.objects.get_or_create(slug='workspace', defaults={'name': 'Workspace', 'created_by': get_user_model().objects.get(username='admin', is_site_admin=True)})"
```

For an invitation-only team, disable self-registration before public access:

```bash
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py shell -c "from apps.accounts.models import SiteSettings; s = SiteSettings.get(); s.registration_enabled = False; s.save()"
```

Create team accounts through **Users** after login. No invitation emails are sent.
Do not load demo accounts into production.

Run the production configuration check:

```bash
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py check --deploy --fail-level WARNING
```

Defaults produce W005/W021 because HSTS subdomain coverage and preload are off.
Enable `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` only when every subdomain supports
HTTPS; decide independently whether to enable `SECURE_HSTS_PRELOAD=True`. The
latter does not submit the domain to a browser preload list. Otherwise record
these two deliberate exceptions; investigate any other warnings.

### 5. Build and serve only public assets

```bash
cd /opt/verity/frontend
sudo -u verity npm ci
sudo -u verity npm run build
sudo install -d -m 755 /var/www/verity /var/www/verity-static
sudo rsync -a --delete --chmod=D755,F644 /opt/verity/frontend/dist/ /var/www/verity/
sudo rsync -a --delete --chmod=D755,F644 /opt/verity/backend/staticfiles/ /var/www/verity-static/
```

These are dedicated deployment directories. Never point the Nginx root at the
repository, backend, virtual environment, or `.env` directory. The `--delete`
commands synchronize only the two public asset directories.

Install the [systemd service](docs/deployment/verity.service):

```bash
sudo cp /opt/verity/docs/deployment/verity.service /etc/systemd/system/verity.service
sudo systemctl daemon-reload
sudo systemctl enable --now verity
sudo systemctl status verity
```

The service uses production settings and sends logs to the journal:

```bash
sudo journalctl -u verity -n 100 --no-pager
```

### 6. Obtain TLS before enabling application traffic

Install the certificate-only [bootstrap configuration](docs/deployment/nginx-bootstrap.conf)
and replace its example domain using `sudoedit`:

```bash
sudo install -d -m 755 /var/www/letsencrypt
sudo cp /opt/verity/docs/deployment/nginx-bootstrap.conf /etc/nginx/sites-available/verity
sudoedit /etc/nginx/sites-available/verity
sudo ln -s /etc/nginx/sites-available/verity /etc/nginx/sites-enabled/verity
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d verity.example.com
```

Substitute your actual domain in the Certbot command as well. Its webroot challenge
requires DNS to reach this server on port 80. The bootstrap site returns 503 for
all non-challenge requests. See the [Certbot webroot documentation](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot).

After the certificate is issued, install the [HTTPS configuration](docs/deployment/nginx.conf)
and replace **every** example domain, including certificate paths:

```bash
sudo cp /opt/verity/docs/deployment/nginx.conf /etc/nginx/sites-available/verity
sudoedit /etc/nginx/sites-available/verity
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Keep the ACME challenge location for renewals. Verify your Certbot installation
schedules renewals, and add a deploy hook to reload Nginx when certificates renew:

```bash
sudo install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx >/dev/null
sudo chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
```

The sample uses per-IP limits for authentication and AI routes; tune them for
shared networks and your provider budget. It disables proxy buffering for AI
responses and sets a 180-second upstream read timeout. Adjust Gunicorn capacity
and timeouts after measuring your workload. See the
[Nginx proxy reference](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering).

### 7. Verify public access

Replace the example domain below:

```bash
curl -I http://verity.example.com/
curl -I https://verity.example.com/
curl https://verity.example.com/api/v1/auth/setup/
curl -i https://verity.example.com/api/v1/items/
```

Expect an HTTP→HTTPS redirect, HTTPS 200 for the frontend,
`{"setup_required":false}`, and 401 for unauthenticated item access. If setup is
still required, close application access and complete admin provisioning first.

In a browser, log in, select **Workspace**, create an item type and an item,
reload a deep link such as `/items/`, and confirm that Django admin CSS loads at
`/admin/` if you use that interface. New accounts still require activation and
vault membership. A login screen is the expected public entry point.

Before relying on the installation, test [backup and restore](docs/operations.md),
review [security boundaries](SECURITY.md), and set up monitoring for HTTP errors,
certificate expiry, disk usage, database backups, and any AI provider spending.
