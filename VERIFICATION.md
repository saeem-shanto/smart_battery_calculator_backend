# Verification — refined backend v1.5.2

## Static checks completed in this build environment

- All Python source files compile successfully with `compileall`.
- Postman collection parses as valid JSON.
- Original client MATLAB files are byte-for-byte unchanged:
  - `battrail.m`: `536383fe9ffe6a248f0970789ada00b791b2554445ccc64cdf14a73617f808bf`
  - `natpaymenttrail.m`: `6898b5d4fad5f4ed27fbb0de6e409a3d0db5c655b60aae75678b755a5bb5a631`
  - `rpresults.m`: `a50f78d4570b0f82d13fe0c3be6fd5d4408747104412a86228b74bbdd4fc48e6`
- The fixed frontend v1.5 calculation contract is preserved:
  - transient workbook validation endpoint unchanged
  - `retain_data=false` transient response unchanged
  - `retain_data=true` guest calculation/token response unchanged
  - admin endpoint paths unchanged
- Added migrations exist for optional user profiles and calculation ownership.
- `.env.example`, `.gitignore`, and `.dockerignore` are present.
- Local SQLite, virtual environments, Python caches, and macOS ZIP metadata are excluded from the final package.

## Runtime checks to run after installing requirements

This isolated build environment could not reach PyPI, so Django/DRF packages could not be installed here. Run the following in the real project environment before deployment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py check
# Automatically uses isolated SQLite/in-memory storage test settings.
python manage.py test
python manage.py spectacular --file openapi.yml --validate
python manage.py octave_status
python manage.py storage_status
```

For production settings:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
```

`python manage.py test` deliberately does not use the Supabase `DATABASE_URL`
or Supabase Storage credentials from `.env`. This prevents Django from creating
and dropping `test_postgres` in the project's remote database.

## End-to-end flows to verify

1. `POST /api/v1/profiles/client-workbook/validate/` with a valid annual file.
2. Calculate with `retain_data=false`; confirm no application calculation/file rows or storage objects are created.
3. Calculate with `retain_data=true`; confirm Postgres metadata + private Supabase input/CSV objects.
4. Retrieve/download the retained guest calculation with `X-Calculation-Token`.
5. Register a user, claim the guest calculation using JWT + the private token, then confirm the old guest token receives 403 and owner JWT succeeds.
6. Upload/download/replace a profile picture and confirm the old avatar object is removed.
7. Staff/admin login, refresh, dashboard list/detail, file download and file deletion.
8. Delete the final calculation referencing an input/result and confirm orphaned Supabase objects are removed.

The included Postman collection now contains the account/ownership checks and no longer ships with a numeric default administrator password.
