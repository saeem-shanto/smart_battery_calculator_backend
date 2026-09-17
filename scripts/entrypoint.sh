#!/bin/sh
set -eu

echo "[entrypoint] Running database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Validating deployment settings..."
python manage.py check --deploy

echo "[entrypoint] Starting server..."
exec "$@"
