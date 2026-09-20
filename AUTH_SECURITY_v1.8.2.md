# Authentication and email security — v1.8.2

## Password recovery contract

Request:

`POST /api/v1/accounts/auth/password-reset/`

```json
{
  "email": "user@example.com"
}
```

First accepted request:

```json
{
  "detail": "If an active account exists for this email, a password reset link has been sent.",
  "resend_after_seconds": 60,
  "resend_available_at": "2026-09-20T17:32:32+09:30"
}
```

The same response is used whether or not the email belongs to an active account. Only a real active account receives an email.

A repeated request inside the cooldown returns HTTP 429 and a `Retry-After` header:

```json
{
  "error": {
    "code": "password_reset_cooldown",
    "message": "Please wait 42 seconds before requesting another email.",
    "fields": null,
    "request_id": "...",
    "retry_after_seconds": 42,
    "retry_at": "2026-09-20T17:32:32+09:30"
  }
}
```

The default cooldown is 60 seconds (`PASSWORD_RESET_RESEND_SECONDS=60`). A broader `password_reset_request` throttle of 10/hour also applies per DRF throttle identity (authenticated user or client IP).

## Email verification and 2FA

OTP challenge responses include the exact resend timing:

```json
{
  "challenge_id": "...",
  "expires_in": 600,
  "resend_after": 60,
  "resend_available_in": 60,
  "resend_available_at": "2026-09-20T17:32:32+09:30",
  "masked_email": "s***@example.com"
}
```

Trying to start or resend a challenge before the timer expires returns HTTP 429 with a purpose-specific cooldown code and retry metadata.

Email send and verification attempts use separate throttle buckets so entering a code does not consume the email-send allowance.

## Provider

Production email continues to use `apps.common.email_backends.BrevoApiEmailBackend` over HTTPS. No SMTP port is required.
