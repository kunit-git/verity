# Operations

[Documentation index](README.md) · [Deployment](../INSTALL.md)

Commands marked Docker run from the repository root. Production commands assume
the layout in INSTALL.md. Substitute your database/user names if customized.
These are operator procedures; normal users should use the application UI.

## Back up and verify

PostgreSQL holds accounts, vault content, item versions, templates, mailbox
artifacts, audit logs, AI conversations, and provider credentials. Preserve the
protected backend `.env`, deployment configuration, and exact Git revision as
well. Build output can be regenerated from code and the frontend lockfile.
Database archives contain private data and secrets; store them outside any public
web root or public repository, with restricted access and an off-host copy.

Docker example:

```bash
umask 077
mkdir -p backups
VERITY_BACKUP_FILE="backups/verity-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db pg_dump -U verity --format=custom --no-owner --no-acl verity > "$VERITY_BACKUP_FILE"
docker compose exec -T db pg_restore --list < "$VERITY_BACKUP_FILE"
git rev-parse HEAD
```

Manual production example, run by a host administrator from a private working
directory (the shell user must be able to write `backups/`):

```bash
umask 077
mkdir -p backups
VERITY_BACKUP_FILE="backups/verity-$(date -u +%Y%m%dT%H%M%SZ).dump"
sudo -u postgres pg_dump --format=custom --no-owner --no-acl verity > "$VERITY_BACKUP_FILE"
pg_restore --list "$VERITY_BACKUP_FILE"
sudo cp --preserve=mode,ownership /opt/verity/backend/.env backups/backend.env
sudo -u verity git -C /opt/verity rev-parse HEAD
```

Check each command's exit status: shell redirection may leave an empty/partial
file if a dump fails. Listing an archive verifies it is readable, not that a
restore will succeed. A database dump does not include PostgreSQL roles; create
the required role separately on a replacement host. See PostgreSQL's
[pg_dump reference](https://www.postgresql.org/docs/16/app-pgdump.html).

Schedule backups according to how much data your team can afford to lose. Record
backup time, source revision, database version, and the result of periodic restore
drills. A container volume on the same host is persistent storage, not a backup.

## Test a restore without replacing live data

Restore into an unused database name, not the database configured for the live
backend. The following example creates `verity_restore_check` in the development
PostgreSQL container; replace the archive path with a real successful backup:

```bash
docker compose exec -T db createdb -U verity -O verity verity_restore_check
docker compose exec -T db pg_restore -U verity --exit-on-error --no-owner --no-acl -d verity_restore_check < backups/CHOSEN_BACKUP.dump
docker compose exec -T -e DB_NAME=verity_restore_check backend python manage.py showmigrations
docker compose exec -T -e DB_NAME=verity_restore_check backend python manage.py shell -c "from apps.vaults.models import Vault; from apps.items.models import Item; print('Vaults:', Vault.objects.count(), 'Items:', Item.objects.count())"
```

For a manual host use `sudo -u postgres createdb --owner=verity verity_restore_check`
and `sudo -u postgres pg_restore --exit-on-error --no-owner --no-acl --role=verity
-d verity_restore_check` with input redirected from the chosen dump. Role and
ownership handling are described in the [pg_restore reference](https://www.postgresql.org/docs/16/app-pgrestore.html).

Complete a restore drill with an isolated application instance using the matching
code revision and restored configuration. Verify login, vault membership, item
versions, tables, and mailbox documents. Do not give a restored staging instance
public access or allow it to send data to an AI provider unintentionally.

To recover live service, schedule downtime, preserve a backup of the current
state, stop the backend, restore into a fresh replacement database, and point the
backend's `DB_NAME` at it. Use the matching application revision, then apply only
planned migrations, start the service, and verify access. Do not run migration
commands before restoring an archive that already contains the schema. Retain
the previous database until recovery is verified.

## Update a manual deployment

Review changes and migration requirements, record the current revision, and take
a verified backup first. The procedure below has downtime; requests can fail
while the backend is stopped.

```bash
sudo systemctl stop verity
sudo -u verity git -C /opt/verity pull --ff-only
sudo -u verity /opt/verity/.venv/bin/pip install -r /opt/verity/backend/requirements.txt
cd /opt/verity/backend
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py migrate
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py seed_data
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py collectstatic --noinput
cd /opt/verity/frontend
sudo -u verity npm ci
sudo -u verity npm run build
sudo rsync -a --delete --chmod=D755,F644 /opt/verity/frontend/dist/ /var/www/verity/
sudo rsync -a --delete --chmod=D755,F644 /opt/verity/backend/staticfiles/ /var/www/verity-static/
sudo systemctl start verity
sudo journalctl -u verity -n 100 --no-pager
```

Stop if any step fails; do not keep running subsequent steps. Run the public
access checks in INSTALL.md after startup. Review Gunicorn updates separately
because it is installed as a deployment dependency. Source rollback alone is not
a database rollback: migrations can be incompatible with older code. Recover the
matching code, configuration, and database backup together when necessary.

For the evaluation Docker stack, back up first, update the checkout, and run
`docker compose up -d --build`. Keep reset/example flags off during upgrades.

## Account recovery

Use the password prompt instead of deleting/recreating an account:

```bash
# Docker
docker compose exec backend python manage.py changepassword admin
```

```bash
# Manual deployment
cd /opt/verity/backend
sudo -u verity env DJANGO_SETTINGS_MODULE=verity.settings.production /opt/verity/.venv/bin/python manage.py changepassword admin
```

Substitute the actual username. If a verified site-admin account is locked, an
operator can reactivate that specific account:

```bash
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(username='admin', is_site_admin=True).update(is_active=True, account_status='active'))"
```

For a manual deployment, use the same `manage.py shell -c` expression with the
production command prefix above. A result of `0` means the named site-admin
account was not found; do not broaden the query to activate unrelated accounts.

`ensure_admin --recreate` actually deletes and recreates a user. Protected
references can prevent deletion, and identity/history relationships make it
unsuitable for routine password resets. Use first-admin setup only for a fresh
installation, before exposing it publicly.

## Logs, certificates, and capacity

- Docker: `docker compose logs --tail=100 backend frontend db`.
- Manual backend: `sudo journalctl -u verity -n 100 --no-pager`.
- Nginx: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`.
- Certificates: check renewal scheduling and run `sudo certbot renew --dry-run`.

Remove tokens, passwords, provider keys, and private content before sharing logs.
Monitor database/disk growth, memory, HTTP failures, backup success, certificate
expiry, and AI provider usage. Table traversals and document generation can grow
with graph size; AI requests occupy backend workers. There are no published
capacity guarantees. Exercise representative data before sizing a deployment.

## Destructive maintenance commands

| Command/control | Actual effect |
| --- | --- |
| `docker compose down -v` | Removes this Compose project's database volume and other managed volumes. |
| `seed_data --reset` / `RECREATE_DB=1` | Drops and recreates the database, then migrates/seeds. |
| `purge_data` | Permanently removes user/content records, then seeds relation types for any remaining vaults; it does not recreate an admin or initial vault. |
| `populate_example` / `LOAD_EXAMPLE=1` | Replaces the six example vaults and the demo user, including edits there. |
| `ensure_admin --recreate` / `RECREATE_ADMIN=1` | Deletes and recreates the configured admin; protected references may prevent it. |

These are not recovery or upgrade commands. Consult [startup controls](configuration.md#docker-startup-controls)
for persistent container flags, and keep backups before intentional resets.
