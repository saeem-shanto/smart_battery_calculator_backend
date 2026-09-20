# Backend refinement history

## v1.8.1 Brevo HTTPS API transport

- Replaced Gmail API/OAuth as the active production transport with a much simpler Brevo REST API backend.
- Render Free remains compatible because all provider traffic is HTTPS, not SMTP.
- Added fixed verified-sender enforcement, timeouts, HTML/plain-text support, CC/BCC, Reply-To, ordinary attachments, diagnostics, tests and production fail-fast checks.
- Password reset, email verification and OTP 2FA behavior above the transport layer is unchanged.
- Added `BREVO_API_SETUP.md` with direct API-key and send smoke tests.

# Backend refinement summary

## v1.7.0 Gmail API transport

- Replaced the production Resend/Anymail transport with a custom Django Gmail REST API backend over HTTPS.
- Uses OAuth2 refresh-token flow; no SMTP port, Gmail App Password, custom sending domain, or Resend account is required.
- Preserves all existing Django `send_mail`/`EmailMultiAlternatives` callers for password reset, email verification, and 2FA.
- Access tokens are cached only in process memory and refreshed automatically; one retry is performed after an HTTP 401.
- Production validates sender email, OAuth client ID/secret, refresh token, and HTTPS frontend URL before startup.
- Added a one-time local OAuth helper (`scripts/get_gmail_refresh_token.py`) that requests only the Gmail send scope and never writes the refresh token to disk.
- Removed Django Anymail from installed apps and runtime requirements.
- Added mocked Gmail backend tests so CI/test runs never contact Google.

## v1.6.0 Render/Resend hardening

- Replaced the production Gmail/SMTP dependency with Resend through Django Anymail over HTTPS.
- Local startup no longer requires `RESEND_API_KEY`; production validates it only when account email is enabled.
- Added provider-aware email readiness checks and provider-neutral email diagnostics.
- Added bounded HTTP timeouts for transactional email.
- 2FA provider outages now surface as HTTP 503.
- Hardened feedback linkage so a historical guest calculation token cannot be reused after account claiming.
- Removed populated environment secrets from the distributable package and added safe local/Render templates plus Git/Docker ignore rules.
- Preserved deterministic content-addressed Supabase Storage keys and all client MATLAB source bytes.

This build preserves the client MATLAB source and the v1.5 frontend calculation contract while strengthening the backend in four areas.

## 1. Privacy and retained-data lifecycle

- `retain_data=false` remains fully transient: no `Calculation`, `StoredInputFile`, or `StoredCsvResult` rows are created and no Supabase Storage objects are written.
- `retain_data=true` stores private artifacts through Django Storage (Supabase S3-compatible storage in production).
- Deleting the final calculation referencing an input/result now removes those orphaned private artifacts after transaction commit.
- Shared content-addressed artifacts are not removed while another calculation references them.

## 2. Optional user accounts

- Registration/login/refresh/logout endpoints added.
- Django's built-in user model remains authoritative: unique username, email, first name, last name, password, staff/superuser flags.
- Private `UserProfile` adds a profile picture stored via the same Supabase Storage backend.
- Authenticated retained calculations are linked to their owner.
- Owners can retrieve/download their own retained calculations using JWT without the guest token.
- Guest retained calculations can be claimed into a user account using both JWT and the original private calculation token.
- Admin users are the same accounts with `is_staff=True`; admin login refuses non-staff accounts before issuing a token.

## 3. Authentication/security refinement

- SimpleJWT refresh-token rotation and blacklisting are enabled.
- Password changes blacklist outstanding refresh tokens and `CHECK_REVOKE_TOKEN` invalidates existing access tokens after password changes.
- Auth and registration endpoints have dedicated throttle scopes.
- Profile image uploads are type/size validated and served through authenticated Django endpoints rather than public storage URLs.
- `.env`, local SQLite DBs, virtual environments, build artifacts and macOS ZIP metadata are excluded from Git/Docker contexts.

## 4. Input/deployment hardening

- Calculation serializer validates supported extensions, empty uploads and configured size limits before execution.
- Client workbook parser now has a hard raw-row cap while streaming XLSX/CSV rows, reducing memory/DoS risk from pathological workbooks.
- Low-level workbook parsing exceptions are no longer echoed to public clients.
- Production PostgreSQL adds connection timeout/application name settings.
- Supabase signed-URL lifetime is configurable even though public API responses use protected Django download endpoints.
- `.env.example` and deployment variables are included.

## Unchanged by design

- `matlab_source/battrail.m`
- `matlab_source/natpaymenttrail.m`
- `matlab_source/rpresults.m`
- Fixed legacy algorithm constants (5 kW PV, retail 0.3773, FiT 0.124, battery annual rate 50, 0-50 kWh search range)
- Existing fixed-frontend endpoints for validation, calculation, calculation-token access and admin dashboard
