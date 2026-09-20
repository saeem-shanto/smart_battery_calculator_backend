# Smart Battery Calculator backend v1.8.1 — verification

## Static/package checks

Run from the project root:

```bash
python -m compileall -q .
python manage.py check
python manage.py test
python manage.py spectacular --file openapi.yml --validate
```

For normal local work:

```bash
unset DJANGO_SETTINGS_MODULE
./scripts/run_dev.sh 127.0.0.1:8000
```

## Email checks

Console-only local configuration:

```bash
python manage.py email_security_status
```

With real Brevo values in `.env`:

```bash
python manage.py brevo_status
python manage.py email_security_status --send-to recipient@example.com
```

Then verify the actual flows:

```text
POST /api/v1/accounts/auth/password-reset/
POST /api/v1/accounts/me/email-verification/request/
POST /api/v1/accounts/auth/token/       (for a user with 2FA enabled)
```

Expected provider success: the Brevo API accepts the message and returns HTTP 201 with a `messageId`. Provider failures must result in an account API HTTP 503, not a false delivery success.

## Production checks

With all Render/Supabase/Brevo environment values present:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py email_security_status
```

Also verify:

```text
GET /api/v1/health/
GET /api/v1/ready/
GET /api/schema/
GET /api/docs/
```

See `BREVO_API_SETUP.md` for direct provider testing outside Django.


## v1.8.2 checks

After upgrading, run `python manage.py migrate`, `python manage.py check`, and `python manage.py test`. Verify a password-reset request returns `resend_after_seconds: 60`; an immediate repeat should return HTTP 429 with `error.code=password_reset_cooldown`, `retry_after_seconds`, `retry_at`, and a matching `Retry-After` header.
