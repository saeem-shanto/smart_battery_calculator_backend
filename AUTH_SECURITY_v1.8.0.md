# Authentication and email security — v1.8.0

Account email verification remains optional. Password recovery and optional email-based 2FA continue to use Django's existing security flows.

## Production email transport

```env
EMAIL_BACKEND=apps.common.email_backends.BrevoApiEmailBackend
BREVO_API_KEY=<secret>
BREVO_SENDER_EMAIL=<verified-sender>
BREVO_SENDER_NAME=Smart Battery Calculator
```

Brevo is called through HTTPS. No SMTP port, Gmail OAuth credential, Gmail App Password, or Resend key is required.

## Failure behavior

Provider/configuration failure does not issue a false success. Security email failure is mapped to HTTP 503 through the existing account API error path. Logs may include provider exception class, HTTP status, and a bounded provider reason, but not API keys, OTP values, password-reset tokens, or message bodies.

## OTP properties

- cryptographically random six numeric digits;
- HMAC-SHA256 digest stored instead of plaintext code;
- exact target email bound to challenge;
- single-use;
- expiry, resend cooldown and attempt limit;
- changing email invalidates relevant pending challenges.
