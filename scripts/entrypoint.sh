#!/bin/sh
set -eu

echo "[entrypoint] Applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Purging expired transient data..."
python manage.py purge_expired_data

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Validating Django deployment settings..."
python manage.py check --deploy

echo "[entrypoint] Validating GNU Octave runtime..."
python manage.py octave_status

echo "[entrypoint] Starting application server..."
exec "$@"
