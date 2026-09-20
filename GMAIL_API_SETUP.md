# Gmail API setup for Smart Battery Calculator

This backend sends account-security email through the Gmail REST API over HTTPS. It does not use SMTP, port 587, or a Gmail App Password.

## 1. Google Cloud

1. Create or select a Google Cloud project.
2. Enable **Gmail API**.
3. Configure the OAuth consent screen.
4. If the app is still in Testing, add the Gmail account that will send the messages as a test user.
5. Create an **OAuth 2.0 Client ID** of type **Desktop app**.
6. Keep the client ID and client secret private.

The one-time authorization helper requests only:

```text
https://www.googleapis.com/auth/gmail.send
```

## 2. Obtain the refresh token locally

In the backend directory:

```bash
source .venv/bin/activate
export GMAIL_API_CLIENT_ID='your-client-id'
export GMAIL_API_CLIENT_SECRET='your-client-secret'
python scripts/get_gmail_refresh_token.py
```

The script opens Google's consent page and waits for a callback on `127.0.0.1:8765`. After approval it prints:

```text
GMAIL_API_REFRESH_TOKEN=...
```

Copy that value into your local `.env` and Render secret environment. Do not commit it.

## 3. Local real-provider test

Set:

```env
ACCOUNT_EMAIL_ENABLED=True
EMAIL_BACKEND=apps.common.email_backends.GmailApiEmailBackend
GMAIL_SENDER_EMAIL=your.address@gmail.com
GMAIL_API_CLIENT_ID=...
GMAIL_API_CLIENT_SECRET=...
GMAIL_API_REFRESH_TOKEN=...
DEFAULT_FROM_EMAIL=Smart Battery Calculator <your.address@gmail.com>
```

Then run:

```bash
python manage.py email_security_status
python manage.py email_security_status --send-to another.address@example.com
```

The second command should send from the authorized Gmail account to the specified recipient.

## 4. Render

Set these secrets/variables in the Render service:

```env
ACCOUNT_EMAIL_ENABLED=True
EMAIL_BACKEND=apps.common.email_backends.GmailApiEmailBackend
GMAIL_SENDER_EMAIL=your.address@gmail.com
GMAIL_API_CLIENT_ID=...
GMAIL_API_CLIENT_SECRET=...
GMAIL_API_REFRESH_TOKEN=...
GMAIL_API_CONNECT_TIMEOUT=5
GMAIL_API_READ_TIMEOUT=15
```

`DEFAULT_FROM_EMAIL` is automatically derived as `Smart Battery Calculator <GMAIL_SENDER_EMAIL>` unless explicitly overridden.

Do not configure `smtp.gmail.com`, `EMAIL_PORT=587`, or a Gmail App Password for the Render deployment.

## 5. OAuth publishing status

Google documents that refresh tokens issued to external OAuth apps in **Testing** publishing status can be time-limited (commonly seven days). For a stable deployment, move the OAuth consent app to the appropriate production publishing status once the integration is validated. Google may require additional consent-screen information or verification depending on the account/app configuration.

## 6. Security behavior

- OAuth client secret and refresh token are read from environment settings only.
- Access tokens are short-lived and cached only in process memory.
- A Gmail API HTTP 401 triggers one token refresh/retry.
- Password-reset URLs, OTPs, OAuth secrets, Authorization headers, and email bodies are not written to provider-error logs.
- Email-provider failures are surfaced to the API as `503 email_unavailable` rather than as invalid user credentials.
