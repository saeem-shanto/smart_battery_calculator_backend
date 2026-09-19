from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Verify the configured PostgreSQL database and retained-file storage backend."

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:
            raise CommandError(f"Database check failed: {type(exc).__name__}: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Database ready: {connection.vendor}"))
        self.stdout.write(f"Supabase storage enabled: {settings.SUPABASE_STORAGE_ENABLED}")
        self.stdout.write(f"Storage backend: {default_storage.__class__.__module__}.{default_storage.__class__.__name__}")

        if settings.SUPABASE_STORAGE_ENABLED:
            try:
                # A HEAD against a deliberately absent key validates bucket,
                # endpoint, credentials and signing without writing user data.
                default_storage.exists("__smart_battery_storage_healthcheck__")
            except Exception as exc:
                raise CommandError(f"Storage check failed: {type(exc).__name__}: {exc}") from exc
            self.stdout.write(self.style.SUCCESS(f"Supabase Storage ready: {settings.SUPABASE_STORAGE_BUCKET}"))
