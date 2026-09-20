# Smart Battery Calculator API

Production Django/DRF backend for Project N01.

## Immutable client MATLAB source

The client MATLAB files remain under `matlab_source/` with their original names and source content:

- `battrail.m`
- `natpaymenttrail.m`
- `rpresults.m`

GNU Octave executes the legacy workflow without renaming or editing those files. The historical runtime input/output names remain:

```text
Vanikavipuldata.xls
Results_RPAtrail400.csv
```

Django creates a temporary compatibility copy named `Vanikavipuldata.xls` only during execution. If the user grants retention permission, the uploaded bytes are stored under their original filename; otherwise processing remains transient and no application file/calculation rows are created.

## Production stack

- Django + Django REST Framework
- Supabase PostgreSQL
- Supabase Storage (private S3-compatible bucket)
- GNU Octave (`octave-cli`)
- original client MATLAB source executed unchanged
- Gunicorn + WhiteNoise
- optional JWT user accounts with name/email/unique username/profile picture
- JWT for staff/admin APIs (same Django user model; staff flag controls admin access)
- guest `X-Calculation-Token` for retained calculations created without an account
- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`
- liveness: `/api/v1/health/`
- readiness: `/api/v1/ready/`

## Retained data: one unique input -> one canonical CSV

Input bytes are content-addressed with SHA-256.

For each unique input payload the system stores at most:

1. one `StoredInputFile`
2. one `StoredCsvResult` named `Results_RPAtrail400.csv`

Re-uploading identical bytes reuses the canonical CSV instead of rerunning Octave while that CSV still exists.

`StoredCsvResult.source_input_sha256` keeps the one-input/one-CSV identity even when an administrator deletes the stored input bytes.

## Calculation records are independent from stored files

A `Calculation` is an audit/history record. It can remain in the database even when an administrator deletes the physical input or output bytes.

Each record can store searchable information such as:

- postcode
- suburb
- state
- arbitrary JSON `metadata`
- original uploaded filename and SHA-256
- calculation assumptions
- warnings
- complete result payload
- runtime and algorithm version
- created/updated timestamps

The admin can therefore retain calculation history in Supabase Postgres while independently removing sensitive input/CSV objects from Supabase Storage.

### Independent deletion behaviour

- delete input file as admin -> calculation record remains; CSV remains
- delete CSV as admin -> calculation record remains; input remains
- delete a calculation record -> orphaned input/CSV objects are removed after the database transaction commits
- if another calculation still references a deduplicated artifact, that shared artifact is preserved
- delete a shared unique file as admin -> every calculation that referenced that file remains, with the corresponding file link set to null

The maintenance command remains a safety net for expired records and any historical orphaned files.

## Main calculation API

```text
POST /api/v1/calculations/client-workbook/
```

Multipart form-data:

```text
file                            File   <client workbook>
retain_data                     Text   true or false
postcode                        Text   5000       (optional)
suburb                          Text   Adelaide   (optional)
state                           Text   SA         (optional)
metadata                        Text   {"scenario_label":"Home A"}  (optional JSON)
battery_installed_cost_per_kwh Text   1000
```

The unchanged MATLAB source fixes the optimisation values for PV size, retail rate, FiT, battery annual payment rate and search bound. `battery_installed_cost_per_kwh` is only used by Django for simple-payback reporting.

## Optional user accounts and profiles

Guest calculation remains supported. Accounts are optional and are useful for cross-device history.

```text
POST /api/v1/accounts/register/
POST /api/v1/accounts/auth/token/
POST /api/v1/accounts/auth/token/refresh/
POST /api/v1/accounts/auth/logout/
GET/PATCH /api/v1/accounts/me/
GET /api/v1/accounts/me/avatar/
POST /api/v1/accounts/me/password/
GET /api/v1/accounts/me/calculations/
```

Profile pictures use the same private Django storage backend as retained calculation files (Supabase Storage in production). The API does not expose S3 credentials or a permanent public object URL.

When an authenticated user creates a retained calculation, the calculation is linked to that user automatically. Owned records are accessible with the owner JWT or staff JWT, not with a guest calculation token. A retained guest calculation can be attached to a logged-in account with:

```text
POST /api/v1/calculations/{public_id}/claim/
Authorization: Bearer <user-access-token>
X-Calculation-Token: <original-private-token>
```

## User calculation access

Retrieve (guest/private-token access):

```text
GET /api/v1/calculations/{public_id}/
X-Calculation-Token: <token>
```

For an owned calculation, use `Authorization: Bearer <user-access-token>` instead. Staff JWTs are also accepted; the guest token is no longer accepted after a calculation is claimed.

List available files:

```text
GET /api/v1/calculations/{public_id}/files/
X-Calculation-Token: <token>
```

Download input or CSV:

```text
GET /api/v1/calculations/{public_id}/files/{file_id}/download/
X-Calculation-Token: <token>
```

Delete the user's calculation record:

```text
DELETE /api/v1/calculations/{public_id}/
X-Calculation-Token: <token>
```

## Admin record table API

The Next.js admin dashboard can use:

```text
GET /api/v1/admin/calculations/
Authorization: Bearer <admin-access-token>
```

The list is deliberately flat/table-ready and includes:

- public ID
- postcode, suburb, state
- status
- original filename and SHA-256
- `has_input_file`
- `has_csv_file`
- optimal battery size
- net annual payment
- estimated bill reduction
- algorithm version
- runtime
- timestamps

Supported filters:

```text
?status=completed
?postcode=5000
?state=SA
?has_input=true
?has_csv=true
?q=Adelaide
```

Admin detail / metadata update / record deletion:

```text
GET    /api/v1/admin/calculations/{public_id}/
PATCH  /api/v1/admin/calculations/{public_id}/
DELETE /api/v1/admin/calculations/{public_id}/
```

The admin can update only the record information fields (`postcode`, `suburb`, `state`, `metadata`); algorithm outputs remain read-only.

## Admin file management

Download:

```text
GET /api/v1/admin/calculations/{public_id}/files/{file_id}/download/
```

Delete input or CSV without deleting the calculation record:

```text
DELETE /api/v1/admin/calculations/{public_id}/files/{file_id}/
```

The delete response reports how many calculation records referenced the shared unique file.

The same deletion capability is also available through Django Admin:

```text
/django-admin/
```

Django Admin contains separate list/table views for:

- calculation records
- unique stored input files
- canonical CSV results

and supports normal single/bulk delete actions.

## Client workbook format

Accepted file types: XLS, XLSX, CSV, TXT.

- column 1: legacy/base PV profile
- column 2: household load
- each accepted row: one hour
- extra columns: ignored with a warning
- production: 8760 rows, or 8784 for leap years

## Supabase production setup

See `SUPABASE_SETUP.md` for the full dashboard/Render setup. In production, `DATABASE_URL` points to Supabase Postgres and retained files use a private Supabase Storage bucket through its S3-compatible endpoint. No retained file bytes are written to PostgreSQL by new v1.5 calculations.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
python manage.py octave_status
python manage.py storage_status
python manage.py runserver 127.0.0.1:8000
```

## Validation commands

```bash
# `manage.py test` automatically uses config.settings.test, which keeps the
# test database/storage isolated from any Supabase values in your .env.
python manage.py test
python manage.py octave_status
python manage.py validate_octave_workbook /path/to/Vanikavipuldata.xls
python manage.py storage_status
python manage.py migrate_binary_artifacts_to_storage --dry-run
python manage.py spectacular --file openapi.yml --validate
python manage.py purge_expired_data
```

If you intentionally want to run an infrastructure integration test against
development settings, opt in explicitly with `DJANGO_SETTINGS_MODULE`; normal
unit tests should never create/drop a database in Supabase.

## Validated parity reference

The full-year client workbook previously reproduced the MATLAB reference closely:

- optimal battery: ~7.388 kWh
- net annual payment: ~$304.15
- export: ~4543.76 kWh
- import: ~1320.37 kWh
- retail price: $0.3773/kWh
- feed-in tariff: $0.124/kWh
- PV size: 5 kW

After migration, run the included Postman production checks before connecting the frontend.


## Privacy / retention mode

`POST /api/v1/calculations/client-workbook/` accepts `retain_data`. When `true`, the unique input, canonical `Results_RPAtrail400.csv`, and calculation record are retained using the existing deduplicated audit model. When `false`, processing is transient: no `Calculation`, `StoredInputFile`, or `StoredCsvResult` rows are created. The response contains the result plus a base64-encoded transient CSV for immediate download. The transient validation endpoint `POST /api/v1/profiles/client-workbook/validate/` also never stores uploaded bytes or parsed values.

## Email security: optional 2FA, email verification, and password recovery (v1.5.9)

The account system keeps email verification optional while separating it cleanly from login 2FA and password recovery.

### Optional email verification

- Registration does **not** require email verification.
- Normal username/password login does **not** require a verified email.
- `GET /api/v1/accounts/me/` now exposes `email_verified` and `email_verified_at`.
- A signed-in user can verify the current account email later through:
  - `GET /api/v1/accounts/me/email-verification/`
  - `POST /api/v1/accounts/me/email-verification/request/`
  - `POST /api/v1/accounts/me/email-verification/resend/`
  - `POST /api/v1/accounts/me/email-verification/verify/`
- Verification OTPs are tied to the exact target email. Changing the profile email invalidates pending challenges and clears verification state.
- Successfully enabling email-based 2FA also verifies the email because the account has proven control of that address.

### Login 2FA

- 2FA is **off by default** for every account.
- A signed-in user or staff member can enable it from their profile.
- Enabling 2FA requires the current password and a 6-digit code sent to the account email.
- After it is enabled, every successful username/password login creates an email OTP challenge; JWT access/refresh tokens are issued only after the OTP is verified.
- OTPs are single-use, expire after `TWO_FACTOR_OTP_TTL_SECONDS`, are limited by `TWO_FACTOR_OTP_MAX_ATTEMPTS`, and can only be resent after `TWO_FACTOR_OTP_RESEND_SECONDS`.
- Users must disable 2FA before changing the account email.

### Forgot password

`POST /api/v1/accounts/auth/password-reset/` now sends a reset email **only** when the submitted address belongs to an active account. If no active account is associated with the email, the API returns HTTP `404` with error code `account_email_not_found` and sends no email.

Email verification is **not required** for password recovery; an active account with an associated but unverified email may still request a password reset. The confirm endpoint remains `POST /api/v1/accounts/auth/password-reset/confirm/`.

### Gmail SMTP production settings

For Gmail SMTP, use a dedicated sender account and a Google **App Password**, not the normal Gmail password. Configure the deployment environment using secrets rather than committed values.

```env
FRONTEND_URL=https://smartbatterycalculator.vercel.app
ACCOUNT_EMAIL_ENABLED=True
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=your-sender@gmail.com
EMAIL_HOST_PASSWORD=<GOOGLE_APP_PASSWORD>
DEFAULT_FROM_EMAIL=Smart Battery Calculator <your-sender@gmail.com>
EMAIL_TIMEOUT=15
PASSWORD_RESET_TIMEOUT_SECONDS=3600
TWO_FACTOR_OTP_TTL_SECONDS=600
TWO_FACTOR_OTP_RESEND_SECONDS=60
TWO_FACTOR_OTP_MAX_ATTEMPTS=5
```

Local development can use either the console email backend or a real SMTP/API provider.

