# v1.5.8.2 — Render deployment fix

## Problem
`collectstatic` failed on Render with `PermissionError: [Errno 13] Permission denied: /app/staticfiles`.

`WORKDIR /app` is created by root. The image later runs as the unprivileged `app` user, so Django could not create `/app/staticfiles`.

## Fix
The Dockerfile now creates `/app/staticfiles` and `/app/media`, recursively assigns `/app` to `app:app`, and only then switches to `USER app`.

Gunicorn timeout is also increased to 360 seconds so it is longer than the configured 300-second Octave timeout.

The startup script no longer runs Octave/storage diagnostics before Gunicorn binds the Render port. Those checks remain available through management commands/readiness endpoints and can be run manually without blocking every cold start.

## Expected deploy sequence
1. Apply migrations
2. Purge expired data
3. Collect static files successfully
4. Start Gunicorn
5. Render health check succeeds
