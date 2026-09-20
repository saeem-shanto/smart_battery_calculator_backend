# v1.5.9 — Email verification and password-recovery refinement

## Added

- Optional account email verification.
- `email_verified` and `email_verified_at` in user profile/auth responses.
- Email-verification status, request, resend, and verify endpoints.
- `verified_email`, `email_verified_at`, and challenge `target_email` persistence.
- Migration `accounts.0003_email_verification`.
- Dedicated `email_verification` throttle scope.
- Swagger/OpenAPI descriptions and response schemas for all new/refined endpoints.

## Changed

- Password reset now returns `404 account_email_not_found` when no active account uses the supplied email and does not send mail.
- Existing unverified emails remain eligible for password reset.
- 2FA setup verifies the exact email address that received the setup OTP.
- Changing an account email clears verification state and invalidates pending email-security challenges.
- OTP resend uses the challenge's stored target email rather than a potentially changed profile email.

## Security note

Returning 404 for an unknown email intentionally allows account enumeration. This is a deliberate product requirement in v1.5.9 rather than the privacy-preserving generic response used previously.

## Deployment

Run:

```bash
python manage.py migrate
python manage.py check
python manage.py test
python manage.py spectacular --file openapi.yml --validate
```

The Render Docker/static-files fix from v1.5.8.2 is retained.
