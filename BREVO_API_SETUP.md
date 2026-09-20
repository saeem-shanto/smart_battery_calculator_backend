# Brevo API setup — Smart Battery Calculator v1.8.0

This is the production email path for Render Free. It uses HTTPS, not SMTP.

## 1. Create a sender in Brevo

In Brevo, open **Settings → Senders, Domains & Dedicated IPs → Senders → Add a sender**.

Use an email address you control. Example:

```text
From name:  Smart Battery Calculator
From email: your-email@example.com
```

If the domain is not already authenticated, Brevo sends a six-digit verification code to that address. Enter the code in Brevo. The sender must show as verified before the API can send transactional email with it.

A Gmail/Outlook sender can be individually verified for a prototype, but a sender on your own authenticated domain is preferable for production deliverability.

## 2. Generate the API key

Open **Settings → SMTP & API → API Keys & MCP → Generate a new API key**.

Name it something recognizable, e.g. `smart-battery-render-production`. Copy the key when Brevo shows it; Brevo does not show the full key again.

This project needs an **API key**, not an SMTP key.

## 3. Verify the API key directly

Do not paste the real key into source code. In your terminal:

```bash
export BREVO_API_KEY='your-real-brevo-api-key'
```

Check authentication:

```bash
curl --fail-with-body --silent --show-error \
  https://api.brevo.com/v3/account \
  -H "accept: application/json" \
  -H "api-key: $BREVO_API_KEY"
```

A successful call returns your Brevo account JSON.

## 4. Send a direct test email before Django

Set these locally:

```bash
export BREVO_SENDER_EMAIL='the-verified-sender@example.com'
export TEST_RECIPIENT='your-other-email@example.com'
```

Then:

```bash
curl --fail-with-body --silent --show-error \
  --request POST \
  --url https://api.brevo.com/v3/smtp/email \
  --header 'accept: application/json' \
  --header "api-key: $BREVO_API_KEY" \
  --header 'content-type: application/json' \
  --data "{
    \"sender\": {
      \"name\": \"Smart Battery Calculator\",
      \"email\": \"$BREVO_SENDER_EMAIL\"
    },
    \"to\": [
      {\"email\": \"$TEST_RECIPIENT\"}
    ],
    \"subject\": \"Smart Battery Calculator - Brevo test\",
    \"textContent\": \"Brevo HTTPS API is working.\"
  }"
```

Expected success is HTTP 201 with JSON containing `messageId`.

## 5. Configure Django locally

In `.env`:

```env
ACCOUNT_EMAIL_ENABLED=True
EMAIL_BACKEND=apps.common.email_backends.BrevoApiEmailBackend
BREVO_API_KEY=<real-api-key>
BREVO_SENDER_EMAIL=<verified-sender-email>
BREVO_SENDER_NAME=Smart Battery Calculator
BREVO_REPLY_TO_EMAIL=
BREVO_API_CONNECT_TIMEOUT=5
BREVO_API_READ_TIMEOUT=15
```

Restart Django, then run:

```bash
python manage.py brevo_status
python manage.py email_security_status
python manage.py email_security_status --send-to your-other-email@example.com
```

`brevo_status` checks the API key and confirms that `BREVO_SENDER_EMAIL` exists in the Brevo account and is active/verified without sending a message.

Then test:

```text
POST /api/v1/accounts/auth/password-reset/
```

## 6. Configure Render

Add these under **Render → Web Service → Environment**:

```env
ACCOUNT_EMAIL_ENABLED=True
EMAIL_BACKEND=apps.common.email_backends.BrevoApiEmailBackend
BREVO_API_KEY=<real-api-key>
BREVO_SENDER_EMAIL=<verified-sender-email>
BREVO_SENDER_NAME=Smart Battery Calculator
BREVO_REPLY_TO_EMAIL=
BREVO_API_CONNECT_TIMEOUT=5
BREVO_API_READ_TIMEOUT=15
```

Remove obsolete production variables if they still exist:

```text
RESEND_API_KEY
GMAIL_SENDER_EMAIL
GMAIL_API_CLIENT_ID
GMAIL_API_CLIENT_SECRET
GMAIL_API_REFRESH_TOKEN
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
```

## Common errors

- **401 / unauthorized**: API key is wrong, expired, deactivated, or not being loaded.
- **400 / invalid sender**: `BREVO_SENDER_EMAIL` is not the exact sender verified in Brevo.
- **403**: Brevo account/security policy or IP authorization is blocking the request; inspect the returned provider reason and Brevo security settings.
- **429**: account/provider rate or sending limit reached.
- **5xx / timeout**: temporary provider/network problem; Django intentionally returns 503 rather than pretending the reset/OTP email was sent.

Never publish your API key in screenshots, Git, Postman exports, frontend environment variables, or browser JavaScript.
