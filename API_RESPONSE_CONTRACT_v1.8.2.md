# API response contract — email security v1.8.2

## Password reset request

`POST /api/v1/accounts/auth/password-reset/`

### 200 — accepted

```json
{
  "detail": "If an active account exists for this email, a password reset link has been sent.",
  "resend_after_seconds": 60,
  "resend_available_at": "2026-09-20T17:32:32+09:30"
}
```

The same response is returned for an unknown email address. This prevents account enumeration.

### 429 — target cooldown

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

Header:

```text
Retry-After: 42
```

### 429 — broader abuse throttle

The broader `password_reset_request` throttle is 10/hour. Its error code is `throttled` and the same `retry_after_seconds`/`Retry-After` metadata is returned.

### 503 — email provider unavailable

```json
{
  "error": {
    "code": "email_unavailable",
    "message": "The security email could not be sent.",
    "fields": null,
    "request_id": "..."
  }
}
```

## OTP challenge response

2FA and email-verification send/resend responses include:

```json
{
  "challenge_id": "4b10...",
  "expires_in": 600,
  "resend_after": 60,
  "resend_available_in": 60,
  "resend_available_at": "2026-09-20T17:32:32+09:30",
  "masked_email": "s***@example.com"
}
```

Trying to send again before the timer expires returns HTTP 429 with a purpose-specific cooldown code, `retry_after_seconds`, `retry_at`, and the `Retry-After` header.

## Recommended frontend behavior

After a successful email send, disable the resend button until `resend_available_at` (normally 60 seconds). On HTTP 429, reset the countdown using `error.retry_after_seconds`. Do not guess the cooldown locally when the API has supplied it.
