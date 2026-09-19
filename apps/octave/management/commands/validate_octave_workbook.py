import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.calculations.services.errors import CalculationEngineExecutionError, CalculationEngineUnavailable
from apps.calculations.services.executor import execute_calculation
from apps.calculations.services.input_builders import build_client_workbook_engine_input
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook


class Command(BaseCommand):
    help = "Run a client workbook through the unchanged MATLAB source under GNU Octave."

    def add_arguments(self, parser):
        parser.add_argument("workbook")
        parser.add_argument("--battery-installed-cost", type=float, default=1000.0)

    def handle(self, *args, **options):
        path = Path(options["workbook"]).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise CommandError(f"Workbook not found: {path}")

        try:
            with path.open("rb") as handle:
                upload = File(handle, name=path.name)
                workbook = parse_client_workbook(upload)
            data, assumptions, warnings = build_client_workbook_engine_input(
                workbook,
                {"battery_installed_cost_per_kwh": options["battery_installed_cost"]},
            )
            execution = execute_calculation(data)
        except (ClientWorkbookError, CalculationEngineUnavailable, CalculationEngineExecutionError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            "input_filename": path.name,
            "detected_format": workbook.detected_format,
            "input_rows": workbook.row_count,
            "engine": execution.engine_version,
            "runtime_ms": execution.runtime_ms,
            "legacy_output_files": sorted(execution.artifacts),
            "assumptions": assumptions,
            "warnings": warnings,
            "result": execution.result,
        }
        self.stdout.write(json.dumps(payload, indent=2, default=str))
        self.stdout.write(self.style.SUCCESS("Workbook calculation completed successfully."))
