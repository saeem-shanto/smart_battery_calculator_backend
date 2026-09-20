# v1.8.2 — Security-email cooldowns and API throttle refinement

## Password reset

`POST /api/v1/accounts/auth/password-reset/` now has production-safe response semantics:

- Existing and non-existing email addresses both receive the same HTTP 200 success body on the first request. This removes account-enumeration through 404 responses.
- The response includes `resend_after_seconds` and `resend_available_at` so the frontend can display a one-minute resend countdown.
- Repeating the same target within the configured cooldown returns HTTP 429 with:
  - `error.code=password_reset_cooldown`
  - `retry_after_seconds`
  - `retry_at`
  - standard `Retry-After` response header.
- The default password-reset resend cooldown is 60 seconds and is configurable with `PASSWORD_RESET_RESEND_SECONDS`.
- The cooldown record stores only an HMAC digest of the normalized target email; the raw email is not persisted for rate limiting.
- If Brevo delivery fails, the password-reset cooldown reservation is released so a provider failure does not unnecessarily lock the user out of retrying.

## OTP and verification email resend

2FA and email-verification email creation/resend now use the same HTTP 429 cooldown contract instead of returning a generic HTTP 400 validation error. Initial challenge creation also respects the resend cooldown, preventing users from bypassing the timer by repeatedly starting a new challenge.

Successful challenge responses now include:

- `resend_after`
- `resend_available_in`
- `resend_available_at`

## Throttle scopes

Email send and code verification traffic now use separate DRF throttle buckets:

- `two_factor_send`: 10/hour
- `two_factor_verify`: 15/minute
- `email_verification_send`: 10/hour
- `email_verification_verify`: 15/minute
- `password_reset_request`: 10/hour
- `password_reset_confirm`: 10/hour

The explicit 60-second target cooldown is applied in addition to the broader DRF abuse ceiling.

## Error envelope

429 responses now expose `retry_after_seconds` and `retry_at` inside the normal API error envelope and include an HTTP `Retry-After` header. DRF's own throttle exceptions receive the same metadata treatment.

## Database

Migration `accounts.0004_security_email_cooldown` adds the privacy-preserving password-reset cooldown table. Stale cooldown rows older than one day are removed by `purge_expired_data`.
