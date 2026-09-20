# Authentication security — v1.5.8

> Historical document: production email transport was superseded in v1.6.0 by Resend through Django Anymail over HTTPS. See `AUTH_SECURITY_v1.6.0.md`.


## Optional login 2FA

2FA is disabled by default. A signed-in account enables it from the profile UI.

Enable flow:

1. `POST /api/v1/accounts/me/two-factor/enable/` with `current_password`.
2. Backend sends a six-digit code to the account email.
3. `POST /api/v1/accounts/me/two-factor/enable/verify/` with `challenge_id` + `code`.
4. `UserProfile.two_factor_enabled` becomes `True`.

Login flow when disabled:

`username + password -> access JWT + refresh JWT`

Login flow when enabled:

`username + password -> email OTP challenge -> OTP verify -> access JWT + refresh JWT`

The backend does not issue JWTs before OTP verification. This applies to normal user login and Django staff/admin login.

OTP controls:

- 6 numeric digits generated with Python `secrets`.
- HMAC-SHA256 digest stored in PostgreSQL; plaintext OTP is never stored.
- Single-use challenge.
- Default 10-minute expiry.
- Default 5 incorrect attempts maximum.
- Default 60-second resend delay.
- Old active challenges for the same purpose are invalidated when a new login/setup challenge is created.
- Expired challenge rows are cleaned by `purge_expired_data`.

## Forgot password

Request:

`POST /api/v1/accounts/auth/password-reset/`

```json
{"email": "user@example.com"}
```

The response is generic whether or not the account exists.

The email links to:

`<FRONTEND_URL>/account/reset-password?uid=<signed-user-id>&token=<django-token>`

Confirm:

`POST /api/v1/accounts/auth/password-reset/confirm/`

```json
{
  "uid": "...",
  "token": "...",
  "new_password": "...",
  "confirm_password": "..."
}
```

Django password validators are applied. Successful reset revokes outstanding refresh tokens. If 2FA was enabled, it remains enabled, so the next login still requires the email OTP.

## Gmail sender configuration

Use a dedicated Gmail/Google Workspace sender account. For SMTP username/password authentication, create a Google App Password for the sender account and store it only as a Render secret.

Required production variables are documented in `.env.example` and `render.yaml`.

Run this after configuration:

```bash
python manage.py email_security_status
python manage.py email_security_status --send-to your-test-address@example.com
```
