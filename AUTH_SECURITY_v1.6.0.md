# Authentication and email security — v1.6.0

## Account model

User accounts remain optional. Registration and normal username/password login do not require email verification. Email verification is available as an authenticated opt-in action. Staff/admin access uses the same Django user model with `is_staff=True`.

## Email transport

Production email is sent through **Resend's HTTPS API** using Django Anymail:

```env
ACCOUNT_EMAIL_ENABLED=True
EMAIL_BACKEND=anymail.backends.resend.EmailBackend
RESEND_API_KEY=re_<secret>
DEFAULT_FROM_EMAIL=Smart Battery Calculator <noreply@verified-domain.example>
```

No SMTP port or Gmail App Password is required on Render. Local development defaults to the console backend and test settings use Django's in-memory email backend.

When email features are enabled in production, startup fails clearly if the Resend backend/API key or HTTPS frontend URL is missing. Provider/network delivery failures are translated into the API's `503 email_unavailable` response rather than being reported as invalid credentials/input.

## Optional email verification

Authenticated endpoints:

- `GET /api/v1/accounts/me/email-verification/`
- `POST /api/v1/accounts/me/email-verification/request/`
- `POST /api/v1/accounts/me/email-verification/resend/`
- `POST /api/v1/accounts/me/email-verification/verify/`

Verification challenges are tied to the exact email address that received the code. Changing the account email clears verification state and consumes pending email-security challenges.

## Optional login 2FA

2FA is off by default. Enabling it requires the current password plus a six-digit email OTP. Once enabled, JWTs are withheld until the login OTP is verified. OTPs are generated with `secrets`, stored only as HMAC-SHA256 digests, expire, are single-use, have a resend delay and have a maximum attempt count.

## Password recovery

Request:

`POST /api/v1/accounts/auth/password-reset/`

Email verification is not required for password recovery. The reset token uses Django's password-reset token generator and becomes invalid after the password changes. Successful reset/password change blacklists outstanding refresh tokens.

The current product contract returns `404 account_email_not_found` for an unknown/inactive email. This intentionally exposes account existence and should be changed to a generic 200 response if privacy against account enumeration becomes a requirement.

## Useful provider check

```bash
python manage.py email_security_status
python manage.py email_security_status --send-to delivered@resend.dev
```
