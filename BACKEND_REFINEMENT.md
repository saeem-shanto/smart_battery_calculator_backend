# Backend refinement summary

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
