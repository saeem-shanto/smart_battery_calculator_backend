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

Django creates a temporary compatibility copy named `Vanikavipuldata.xls` only during execution. The user's uploaded file is stored under its original filename while that stored input exists.

## Production stack

- Django + Django REST Framework
- PostgreSQL
- GNU Octave (`octave-cli`)
- original client MATLAB source executed unchanged
- Gunicorn + WhiteNoise
- JWT for staff/admin APIs
- one-time guest `X-Calculation-Token`
- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`
- liveness: `/api/v1/health/`
- readiness: `/api/v1/ready/`

## One unique input -> one canonical CSV

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

The admin can therefore retain the calculation history while removing large or sensitive file blobs.

### Independent deletion behaviour

- delete input file -> calculation record remains; CSV remains
- delete CSV -> calculation record remains; input remains
- delete calculation record -> stored files are not automatically deleted
- delete a shared unique file -> every calculation that referenced that file remains, with the corresponding file link set to null

The maintenance command can later remove genuinely unreferenced files.

## Main calculation API

```text
POST /api/v1/calculations/client-workbook/
```

Multipart form-data:

```text
file                            File   <client workbook>
consent                         Text   true
postcode                        Text   5000       (optional)
suburb                          Text   Adelaide   (optional)
state                           Text   SA         (optional)
metadata                        Text   {"scenario_label":"Home A"}  (optional JSON)
battery_installed_cost_per_kwh Text   1000
```

The unchanged MATLAB source fixes the optimisation values for PV size, retail rate, FiT, battery annual payment rate and search bound. `battery_installed_cost_per_kwh` is only used by Django for simple-payback reporting.

## User calculation access

Retrieve:

```text
GET /api/v1/calculations/{public_id}/
X-Calculation-Token: <token>
```

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

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
python manage.py octave_status
python manage.py runserver 127.0.0.1:8000
```

## Validation commands

```bash
python manage.py test
python manage.py octave_status
python manage.py validate_octave_workbook /path/to/Vanikavipuldata.xls
python manage.py spectacular --file openapi.yml --validate
python manage.py purge_expired_data
```

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
