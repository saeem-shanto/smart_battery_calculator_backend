# v1.6.1 — local static/runtime refinement

## Problem observed
Running `python manage.py runserver` while the shell had
`DJANGO_SETTINGS_MODULE=config.settings.production` caused DRF's browsable API
to request static assets through `CompressedManifestStaticFilesStorage`. Without
a prior `collectstatic`, Django raised `Missing staticfiles manifest entry`.

## Changes
- Development settings now use `StaticFilesStorage`; local development does not
  require a manifest or `collectstatic`.
- Production DRF responses are JSON-only, so normal API endpoints no longer
  depend on browsable-API CSS. Swagger and Redoc stay available separately.
- Added `scripts/run_dev.sh`, which explicitly selects development settings.
- Render/Docker production continues to run `collectstatic --noinput --clear`
  before Gunicorn starts.

## Local usage
```bash
unset DJANGO_SETTINGS_MODULE
./scripts/run_dev.sh 127.0.0.1:8000
```

Or:
```bash
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py runserver 127.0.0.1:8000
```

## Production-like local verification
```bash
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py collectstatic --noinput
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
```
