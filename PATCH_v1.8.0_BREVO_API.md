# v1.8.0 — Brevo HTTPS transactional email

## Why

Render Free restricts common SMTP ports. Gmail OAuth was functional but too complex for this project. Resend test mode restricted arbitrary recipients until a domain was verified.

## Change

Production email now uses a custom Django `BrevoApiEmailBackend` calling Brevo's transactional REST endpoint over HTTPS.

Required production secrets:

```text
BREVO_API_KEY
BREVO_SENDER_EMAIL
```

Optional settings:

```text
BREVO_SENDER_NAME
BREVO_REPLY_TO_EMAIL
BREVO_API_CONNECT_TIMEOUT
BREVO_API_READ_TIMEOUT
```

Password reset, email verification and email OTP 2FA are unchanged above the transport layer.

## Security properties

- API key is environment-only.
- API key is never logged.
- provider errors are bounded/sanitized before logging.
- production fails fast when Brevo is enabled but credentials are absent.
- sender is fixed by server-side settings, preventing callers from selecting an arbitrary unverified From address.
- sends are not automatically retried after ambiguous network failures, reducing duplicate OTP/reset messages.
