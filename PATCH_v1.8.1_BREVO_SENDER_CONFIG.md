# v1.8.1 — Brevo sender configuration refinement

## Fixed

- Removed the redundant production requirement to keep `DEFAULT_FROM_EMAIL` manually synchronized with `BREVO_SENDER_EMAIL`.
- When the Brevo API backend is active, Django now derives `DEFAULT_FROM_EMAIL` automatically from `BREVO_SENDER_NAME` + `BREVO_SENDER_EMAIL`.
- The Brevo backend remains authoritative for the actual API `sender`, preventing caller-controlled From spoofing.
- This prevents stale values left by previous Resend/Gmail configurations from blocking Django startup before `brevo_status` can run.

## Local command

Use development settings explicitly when diagnosing locally:

```bash
unset DJANGO_SETTINGS_MODULE
DJANGO_SETTINGS_MODULE=config.settings.development python manage.py brevo_status
```

Set `EMAIL_BACKEND=apps.common.email_backends.BrevoApiEmailBackend` plus `BREVO_API_KEY` and `BREVO_SENDER_EMAIL` in `.env` to test Brevo locally.
