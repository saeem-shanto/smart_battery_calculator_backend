# Smart Battery Calculator Backend v1.5.2 — Postman Test Guide

## Import
Import these two JSON files into Postman:

1. `Smart_Battery_Backend_v1.5.2_COMPLETE.postman_collection.json`
2. `Smart_Battery_Backend_v1.5.2_Local.postman_environment.json`

Select the **Smart Battery Backend v1.5.2 - Local** environment.

## Start Django

```bash
source .venv/bin/activate
python manage.py runserver
```

Default base URL in the environment:

`http://127.0.0.1:8000`

## Test file
For multipart requests with a `file` field, select:

`Postman_Test_Profile_8760.csv`

It contains 8760 synthetic hourly rows and is intended only for API/integration testing.

## Admin credentials
Set the Postman environment values:

- `adminUsername`
- `adminPassword`

Use a real Django staff/superuser account. Do not leave placeholder credentials.

## Recommended run order

1. `00 - System & Documentation`
2. `01 - Public Support APIs`
3. `02 - Calculation End-to-End`
4. `03 - Optional User Accounts & Ownership`
5. `04 - Admin Authentication & Calculation Audit`
6. `05 - Admin Tariff CRUD`
7. `06 - Optional GNU Octave Diagnostics`
8. `07 - Privacy & Field Validation`
9. `08 - Account Security / Session Lifecycle`
10. `99 - DESTRUCTIVE Cleanup Checks` **last**

The collection contains **59 requests**. Test scripts automatically capture JWTs, calculation public IDs/tokens, stored file IDs, and tariff IDs into environment variables.

## Important privacy checks

### Transient calculation
`retain_data=false` should return HTTP 200 with:
- `public_id: null`
- `access_token: null`
- `files: []`
- `transient_csv` populated

### Retained guest calculation
`retain_data=true` should return HTTP 201 with a calculation `public_id` and guest `access_token`, plus stored file metadata.

### Owned calculation
When an authenticated user performs a retained calculation, ownership is through the Bearer JWT; a guest calculation can also be claimed with the original `X-Calculation-Token`.

## Final backend checks

```bash
python manage.py check
python manage.py test
python manage.py spectacular --file openapi.yml --validate
python manage.py octave_status
python manage.py storage_status
```
