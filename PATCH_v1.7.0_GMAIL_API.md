# v1.7.0 — Gmail API email transport

## Why

The project owner wants security email to originate from an authorized Gmail account and reach normal external recipients. Render Free does not provide outbound SMTP on the usual mail ports, while Resend's test domain restricts normal recipients until a custom sender domain is verified.

## Change

- Added `apps.common.email_backends.GmailApiEmailBackend`.
- Sends standard Django MIME messages with Gmail `users.messages.send` over HTTPS.
- Exchanges a stored OAuth refresh token for short-lived access tokens at Google's OAuth token endpoint.
- Caches access tokens in process memory and retries once after HTTP 401.
- Uses only the Gmail send OAuth scope during the included one-time authorization helper.
- Removed Django Anymail/Resend from the active settings, Render template, installed apps, and requirements.
- Preserved password-reset, optional email verification, and 2FA endpoint behavior.
- Added provider-aware readiness checks and mocked backend tests.

## Required production secrets

```env
GMAIL_SENDER_EMAIL=your.address@gmail.com
GMAIL_API_CLIENT_ID=...
GMAIL_API_CLIENT_SECRET=...
GMAIL_API_REFRESH_TOKEN=...
```

Do not commit these values.
