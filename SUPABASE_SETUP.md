# Supabase production setup

This release uses Supabase for both persistent layers:

- **Database:** Supabase PostgreSQL for Django models, admin records, metadata, results and audit history.
- **Files:** Supabase Storage for retained input workbooks, the canonical `Results_RPAtrail400.csv`, and optional user profile pictures.

The privacy-safe `retain_data=false` path remains transient and does not create a Django database row or Supabase Storage object.

## 1. Create / choose the Supabase project

Use one Supabase project for the backend. Keep its database password and S3 credentials out of Git.

## 2. Configure PostgreSQL

In Supabase Dashboard, open **Connect** and copy the **Session Pooler** connection string. Session mode is a good fit for the long-running Render Django service and avoids IPv4/IPv6 deployment surprises.

Set it on Render as `DATABASE_URL`. Use the exact value Supabase provides. If the database password contains reserved URL characters, percent-encode the password before putting it in a URL. If necessary, add:

```text
?sslmode=require
```

Example shape only:

```text
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@<POOLER_HOST>:5432/postgres?sslmode=require
```

Do not copy the example host literally; use the value shown by your project.

## 3. Create a private Storage bucket

In **Storage**, create a private bucket:

```text
smart-battery-files
```

Do not make this bucket public. User/admin downloads are authenticated by Django and streamed through the existing API endpoints.

## 4. Enable S3 access

In Supabase Storage S3 settings:

1. Enable the S3 protocol if required by the project settings.
2. Generate a server-side S3 access-key pair.
3. Copy the endpoint and region shown by Supabase.

Prefer the direct storage hostname, with this general shape:

```text
https://<PROJECT_REF>.storage.supabase.co/storage/v1/s3
```

The exact endpoint and region must come from the Supabase dashboard.

## 5. Render environment variables

Set:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
DATABASE_URL=<Supabase Session Pooler URL>

SUPABASE_STORAGE_ENABLED=True
SUPABASE_STORAGE_BUCKET=smart-battery-files
SUPABASE_S3_ENDPOINT=<Supabase S3 endpoint>
SUPABASE_S3_REGION=<Supabase S3 region>
SUPABASE_S3_ACCESS_KEY_ID=<server-side access key id>
SUPABASE_S3_SECRET_ACCESS_KEY=<server-side secret key>
```

Keep the S3 access key and secret in Render secrets only. Never expose them through `NEXT_PUBLIC_*`, frontend code, Postman collection variables or Git.

## 6. Deploy and migrate Django

The container entrypoint applies Django migrations automatically. You can also run manually:

```bash
python manage.py migrate
python manage.py storage_status
```

`storage_status` verifies:

- PostgreSQL connectivity
- configured Django storage backend
- access to the Supabase Storage bucket

## 7. Move any v1.4 database blobs to Supabase Storage

v1.5 keeps the old BinaryField columns nullable only to support a safe migration from previous releases. New retained calculations write directly to Supabase Storage and leave those binary columns empty.

First inspect:

```bash
python manage.py migrate_binary_artifacts_to_storage --dry-run
```

Then migrate:

```bash
python manage.py migrate_binary_artifacts_to_storage
```

The command uploads each legacy input/CSV, verifies the object exists, and then clears the old PostgreSQL binary data. It is safe to rerun.

## 8. Object layout

Input objects are content-addressed:

```text
inputs/<sha-prefix>/<input-sha256>/input.bin
```

CSV objects are deterministic:

```text
results/<sha-prefix>/<input-sha256>/Results_RPAtrail400.csv
```

Profile pictures use private per-user paths:

```text
profiles/<user-id>/avatars/<random-id>_<sanitized-name>.<ext>
```

The original calculation upload filename remains stored in PostgreSQL and is used when Django returns the file to the user/admin. Profile picture object URLs are not exposed as permanent public URLs; the authenticated Django endpoint streams the file.

## 9. Delete behavior

When an admin deletes a `StoredInputFile` or `StoredCsvResult`, the database row is deleted and a `post_delete` hook removes the corresponding Supabase Storage object after the database transaction commits.

When a calculation record is deleted, the backend checks its content-addressed input/CSV after commit. If no other calculation still references an artifact, the orphaned row/object is removed immediately. Shared artifacts remain until their final calculation reference is deleted.

Direct admin file deletion still preserves calculation history because calculation file foreign keys use `SET_NULL`.

## 10. Security model

- Supabase Storage bucket: private.
- S3 access credentials: backend/server only.
- Browser never receives S3 credentials.
- Browser downloads through Django's existing token/admin-authenticated endpoints.
- `retain_data=false`: no Supabase Postgres calculation row and no Supabase Storage object.
