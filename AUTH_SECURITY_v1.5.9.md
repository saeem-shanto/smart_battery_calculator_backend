# Authentication and email security — v1.5.9

> Historical document: production email transport was superseded in v1.6.0 by Resend through Django Anymail over HTTPS. See `AUTH_SECURITY_v1.6.0.md`.


## Behaviour contract

### Registration and login

Email verification is optional. A user may register without an email, register with an unverified email, and use normal username/password login without verifying that address. The profile API exposes the current verification state through `email_verified` and `email_verified_at`.

### Optional email verification

Authenticated endpoints:

- `GET /api/v1/accounts/me/email-verification/` — current verification status.
- `POST /api/v1/accounts/me/email-verification/request/` — send a six-digit OTP to the current account email.
- `POST /api/v1/accounts/me/email-verification/resend/` — resend an existing verification challenge after the configured delay.
- `POST /api/v1/accounts/me/email-verification/verify/` — verify the OTP.

A challenge stores the exact `target_email` that received the OTP. Verification succeeds only if that target still matches the user's current email. Updating the account email clears `verified_email`/`email_verified_at` and consumes any pending email-security challenges.

### Optional login 2FA

2FA remains off by default. Enabling it requires the current password and an email OTP. Successful 2FA setup also marks the current email as verified because control of that exact address was demonstrated. Once enabled, JWTs are withheld until the login OTP is verified.

### Password recovery

Request:

`POST /api/v1/accounts/auth/password-reset/`

```json
{
  "email": "user@example.com"
}
```

If the email belongs to an active account, the API sends one password-reset email and returns HTTP 200:

```json
{
  "detail": "Password reset email sent."
}
```

If no active account is associated with the email, the API sends no email and returns HTTP 404 with the standard API error envelope and code `account_email_not_found`. This behaviour intentionally exposes account existence because it is the requested product rule.

Email verification is not required for password recovery.

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

Django password validators are applied. A successful reset revokes outstanding refresh tokens. Existing 2FA remains enabled.

## OTP controls

- six numeric digits generated with Python `secrets`;
- HMAC-SHA256 digest stored, never the plaintext OTP;
- exact target email stored on the challenge;
- single-use;
- configurable expiry, resend delay, and attempt limit;
- old same-purpose challenges invalidated when a new challenge is created;
- email changes invalidate pending challenges.

## Swagger/OpenAPI

The OpenAPI version is `1.5.9`. Password reset documents 200/400/404/503 responses, and the email-verification status/request/resend/verify endpoints are included under **User Accounts**.
