#!/bin/sh
set -eu

echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Purging expired transient/security data..."
python manage.py purge_expired_data

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Starting application server..."
exec "$@"
