#!/bin/sh
set -eu

# Always use development settings for local runserver, even if the parent
# shell previously exported DJANGO_SETTINGS_MODULE=config.settings.production.
export DJANGO_SETTINGS_MODULE=config.settings.development

if [ "$#" -eq 0 ]; then
    set -- 127.0.0.1:8000
fi

exec python manage.py runserver "$@"
