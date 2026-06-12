#!/usr/bin/env bash
#
# Container entrypoint for the Verity backend.
#
# On every start it waits for Postgres, brings the schema up to date
# (running migrations only when there is something to apply), seeds the
# built-in relation types, and ensures the admin account exists.
#
# Two env flags let you trigger destructive resets without editing this file:
#   RECREATE_DB=1      drop and recreate the database, then migrate + seed
#   RECREATE_ADMIN=1   delete and recreate the admin user
#
set -euo pipefail

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

is_true() {
    case "${1:-}" in
        1 | true | TRUE | yes | YES | on | ON) return 0 ;;
        *) return 1 ;;
    esac
}

echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os, sys, time
import psycopg

host = os.environ.get("DB_HOST", "db")
port = os.environ.get("DB_PORT", "5432")
user = os.environ.get("DB_USER", "verity")
password = os.environ.get("DB_PASSWORD", "verity_dev")

deadline = time.time() + 60
while True:
    try:
        psycopg.connect(
            f"host={host} port={port} user={user} password={password} dbname=postgres"
        ).close()
        break
    except Exception as exc:  # noqa: BLE001
        if time.time() > deadline:
            print(f"Database not reachable after 60s: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PY
echo "Database is ready."

if is_true "${RECREATE_DB:-0}"; then
    echo "RECREATE_DB set — dropping and recreating the database..."
    python manage.py seed_data --reset
else
    echo "Applying database migrations..."
    python manage.py migrate --noinput
    python manage.py seed_data
fi

if is_true "${RECREATE_ADMIN:-0}"; then
    echo "RECREATE_ADMIN set — recreating the admin user..."
    python manage.py ensure_admin --recreate
else
    python manage.py ensure_admin
fi

if is_true "${LOAD_EXAMPLE:-0}"; then
    echo "LOAD_EXAMPLE set — loading example vaults..."
    python manage.py populate_example
fi

echo "Starting: $*"
exec "$@"
