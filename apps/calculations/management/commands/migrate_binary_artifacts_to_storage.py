from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.calculations.models import StoredCsvResult, StoredInputFile


class Command(BaseCommand):
    help = (
        "Move legacy BinaryField input/CSV bytes into the configured Django file storage "
        "(Supabase Storage in production). Safe to rerun."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--keep-binary",
            action="store_true",
            help="Do not clear legacy PostgreSQL BinaryField data after a verified storage upload.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        keep_binary = options["keep_binary"]
        migrated_inputs = 0
        migrated_csv = 0
        skipped = 0

        for obj in StoredInputFile.objects.all().iterator():
            if obj.storage_file and obj.storage_file.name:
                skipped += 1
                continue
            if obj.data is None:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"Would migrate input {obj.id} {obj.canonical_filename}")
                continue
            raw = bytes(obj.data)
            obj.storage_file.save(obj.canonical_filename, ContentFile(raw), save=False)
            if not obj.storage_file.storage.exists(obj.storage_file.name):
                raise RuntimeError(f"Storage verification failed for input {obj.id}")
            if not keep_binary:
                obj.data = None
                obj.save(update_fields=["storage_file", "data", "updated_at"])
            else:
                obj.save(update_fields=["storage_file", "updated_at"])
            migrated_inputs += 1

        for obj in StoredCsvResult.objects.all().iterator():
            if obj.storage_file and obj.storage_file.name:
                skipped += 1
                continue
            if obj.data is None:
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"Would migrate CSV {obj.id} {obj.filename}")
                continue
            raw = bytes(obj.data)
            obj.storage_file.save(obj.filename, ContentFile(raw), save=False)
            if not obj.storage_file.storage.exists(obj.storage_file.name):
                raise RuntimeError(f"Storage verification failed for CSV {obj.id}")
            if not keep_binary:
                obj.data = None
                obj.save(update_fields=["storage_file", "data"])
            else:
                obj.save(update_fields=["storage_file"])
            migrated_csv += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Migration complete: {migrated_inputs} input file(s), {migrated_csv} CSV file(s), {skipped} skipped."
            )
        )
