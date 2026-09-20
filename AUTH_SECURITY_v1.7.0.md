# Authentication and email security — v1.7.0

## Account model

User accounts remain optional. Registration and normal username/password login do not require email verification. Staff/admin access uses the same Django user model with `is_staff=True`.

## Gmail API delivery

Production security email is sent through the Gmail REST API over HTTPS using the Gmail account explicitly authorized by the project owner:

```env
EMAIL_BACKEND=apps.common.email_backends.GmailApiEmailBackend
GMAIL_SENDER_EMAIL=your.address@gmail.com
GMAIL_API_CLIENT_ID=<client-id>
GMAIL_API_CLIENT_SECRET=<client-secret>
GMAIL_API_REFRESH_TOKEN=<refresh-token>
DEFAULT_FROM_EMAIL=Smart Battery Calculator <your.address@gmail.com>
```

The transport does not use SMTP, port 587, or a Gmail App Password. Existing Django email callers are unchanged. The OAuth refresh token is stored only as an environment secret; short-lived access tokens are cached in process memory and refreshed automatically.

The requested OAuth scope is `https://www.googleapis.com/auth/gmail.send` only. For a stable deployment, the Google OAuth app should not remain indefinitely in external Testing mode because testing refresh tokens can be time-limited.

Provider/network failures are translated into `503 email_unavailable` for email-security flows. Logs expose only a bounded provider status/reason and never credentials, OTP values, reset URLs/tokens, message bodies, or Authorization headers.

## Optional email verification

Email verification remains opt-in. Verification challenges are tied to the exact address that received the OTP. Changing the account email clears verification state and consumes pending email-security challenges.

## Optional login 2FA

2FA remains off by default. Enabling it requires the current password and a six-digit email OTP. Once enabled, JWTs are withheld until the login OTP is verified. OTPs are generated with `secrets`, stored as HMAC-SHA256 digests, expire, are single-use, have a resend delay, and have a maximum attempt count.

## Password recovery

`POST /api/v1/accounts/auth/password-reset/` sends a reset email only when the submitted address belongs to an active account. The current product contract returns `404 account_email_not_found` for an unknown/inactive email, which intentionally exposes account existence.

Email verification is not required for password recovery. Successful reset revokes outstanding refresh tokens while existing 2FA remains enabled.

## Operational checks

```bash
python manage.py email_security_status
python manage.py email_security_status --send-to recipient@example.com
```

For one-time OAuth setup:

```bash
export GMAIL_API_CLIENT_ID='...'
export GMAIL_API_CLIENT_SECRET='...'
python scripts/get_gmail_refresh_token.py
```
