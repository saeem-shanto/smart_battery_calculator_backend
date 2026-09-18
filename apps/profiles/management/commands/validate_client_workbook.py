from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook


class Command(BaseCommand):
    help = "Validate a client two-column PV/load workbook without running MATLAB."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to XLS/XLSX/CSV/TXT client workbook")

    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise CommandError(f"File not found: {path}")

        upload = SimpleUploadedFile(path.name, path.read_bytes())
        try:
            data = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("Client workbook is valid."))
        self.stdout.write(f"Format: {data.detected_format}")
        self.stdout.write(f"Rows: {data.row_count}")
        self.stdout.write(f"PV min/max: {min(data.pv_base_profile):.6g} / {max(data.pv_base_profile):.6g}")
        self.stdout.write(f"Load min/max: {min(data.load_profile):.6g} / {max(data.load_profile):.6g}")
        if data.warnings:
            self.stdout.write("Warnings:")
            for warning in data.warnings:
                self.stdout.write(f"  - {warning}")
