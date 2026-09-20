# v1.6.2 — Resend provider diagnostics

## Why
The password-reset endpoint correctly returned HTTP 503 when Anymail/Resend rejected a send, but logs only reported `AnymailRequestsAPIError`, hiding the provider HTTP status and error reason.

## Changes
- Added a safe provider error summarizer that logs only exception type, HTTP status, and provider response message.
- Authorization headers, API keys, reset URLs/tokens, OTP values, request payloads, and email bodies are never logged.
- `email_security_status --send-to ...` now prints the safe provider failure reason.
- The command warns when a `@resend.dev` testing sender is configured and directs smoke tests to `delivered@resend.dev`.

## Recommended diagnosis
```bash
python manage.py email_security_status --send-to delivered@resend.dev
```

Interpretation:
- success: API key + Anymail + HTTPS path are healthy; verify a custom sending domain for real recipients;
- HTTP 401: API key invalid/missing/revoked or wrong team;
- HTTP 403: sender/domain or permission restriction; inspect Resend Logs;
- HTTP 429: rate limit/quota;
- HTTP 5xx or timeout: transient provider/network issue.
