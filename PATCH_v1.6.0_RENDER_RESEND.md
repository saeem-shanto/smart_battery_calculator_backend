# v1.6.0 — Render/Resend production hardening

This patch changes deployment/email configuration without changing the client MATLAB source or the calculator result contract.

## Resend over HTTPS

- Production uses `anymail.backends.resend.EmailBackend`.
- `RESEND_API_KEY` is validated only when account email features are enabled.
- Local development defaults to Django's console backend, so a missing API key no longer prevents `runserver` from starting.
- `email_security_available()` now understands Resend, local test backends and optional SMTP instead of assuming every real backend is SMTP.
- Anymail connect/read timeouts are configurable with `EMAIL_API_CONNECT_TIMEOUT` and `EMAIL_API_READ_TIMEOUT`.
- The email diagnostic command is provider-neutral and can send a real test message.
- 2FA login now reports provider outages as HTTP 503 rather than incorrectly treating them as request-validation errors.

## Render/Supabase hardening

- `render.yaml` no longer configures Gmail/port 587.
- Production requires Supabase PostgreSQL and private Supabase Storage when retained data is enabled.
- PostgreSQL connection timeouts are applied in base settings as well as production.
- TLS/proxy/cookie/HSTS production settings remain explicit.

## Authorization refinement

- A guest calculation's private token stops authorizing feedback linkage after that calculation is claimed by an account.
- Claimed calculations can be linked to feedback only by their authenticated owner or staff/admin.

## Secret hygiene

- The populated `sbc_backend.env` was intentionally removed from the distributable package.
- Added `.env.example`, `render.env.example`, `.gitignore`, and `.dockerignore`.
- Real PostgreSQL, Supabase Storage and Resend credentials must remain in the local environment or Render secret variables.

## Verification commands

```bash
python -m compileall -q apps config manage.py
python manage.py check
python manage.py test
python manage.py spectacular --file openapi.yml --validate
python manage.py email_security_status
python manage.py email_security_status --send-to delivered@resend.dev
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
```
