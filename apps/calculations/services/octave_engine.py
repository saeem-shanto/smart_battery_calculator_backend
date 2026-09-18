from __future__ import annotations

import csv
import math
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from django.conf import settings

from .interfaces import EngineInput


class OctaveUnavailable(RuntimeError):
    """Raised when GNU Octave / octave-cli is not installed or accessible."""


class OctaveExecutionError(RuntimeError):
    """Raised when the client algorithm fails inside GNU Octave."""


class OctaveEngine:
    """
    Execute the client MATLAB-compatible algorithm using GNU Octave.

    This engine intentionally starts a short-lived octave-cli process for each
    calculation. Calls are serialized by default so a 512 MB Render instance
    cannot launch multiple Octave calculations concurrently inside one worker.
    """

    version = "gnu-octave-client-algorithm-v1"
    _call_lock = threading.Lock()
    RESULT_MARKER = "__SMART_BATTERY_RESULT__"

    RESULT_FIELDS = (
        "optimal_battery_size_kwh",
        "net_annual_payment_aud",
        "export_to_grid_kwh_year",
        "import_from_grid_kwh_year",
        "energy_balance_import_minus_export_kwh_year",
        "average_retail_price_aud_per_kwh",
        "battery_annual_payment_rate_aud_per_kwh_year",
        "average_feed_in_tariff_aud_per_kwh",
        "pv_size_kw",
        "objective_value",
        "optimizer_exitflag",
        "baseline_annual_payment_aud",
        "estimated_annual_bill_reduction_aud",
        "estimated_annual_bill_reduction_percent",
        "battery_upfront_cost_aud",
        "simple_payback_years",
        "self_consumption_percent",
        "baseline_self_consumption_percent",
        "annual_load_kwh",
        "annual_pv_generation_kwh",
    )

    def __init__(self) -> None:
        self.executable = settings.OCTAVE_EXECUTABLE
        self.timeout_seconds = settings.OCTAVE_TIMEOUT_SECONDS
        self.source_dir = Path(settings.BASE_DIR) / "octave_source"

    @staticmethod
    def _quote_octave_string(value: str) -> str:
        # MATLAB/Octave escape a single quote inside a quoted string by doubling it.
        return value.replace("'", "''")

    def _resolve_executable(self) -> str:
        path = shutil.which(self.executable)
        if not path:
            raise OctaveUnavailable(
                f"GNU Octave executable {self.executable!r} was not found. "
                "Install GNU Octave (the Docker image in this project does this automatically)."
            )
        return path

    def status(self) -> dict[str, Any]:
        path = shutil.which(self.executable)
        if not path:
            return {
                "engine": self.version,
                "runtime_ready": False,
                "octave_executable": self.executable,
                "octave_path": None,
                "octave_version": None,
                "algorithm_source_present": (self.source_dir / "smart_battery_optimize.m").exists(),
                "error": f"{self.executable!r} was not found on PATH.",
            }

        version = None
        error = None
        try:
            proc = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            first_line = (proc.stdout or proc.stderr).splitlines()
            version = first_line[0].strip() if first_line else None
            if proc.returncode != 0:
                error = (proc.stderr or proc.stdout).strip()[-1000:]
        except Exception as exc:  # pragma: no cover - platform/process specific
            error = f"{type(exc).__name__}: {exc}"

        source_ready = all(
            (self.source_dir / name).exists()
            for name in ("smart_battery_optimize.m", "run_smart_battery_cli.m")
        )
        return {
            "engine": self.version,
            "runtime_ready": bool(path and source_ready and not error),
            "octave_executable": self.executable,
            "octave_path": path,
            "octave_version": version,
            "algorithm_source_present": source_ready,
            "serialize_calls": bool(settings.OCTAVE_SERIALIZE_CALLS),
            "timeout_seconds": self.timeout_seconds,
            "error": error,
        }

    @staticmethod
    def _write_vector(path: Path, values: list[float]) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            for value in values:
                writer.writerow([format(float(value), ".17g")])

    def _validate(self, data: EngineInput) -> tuple[float, float]:
        if len(data.load_kwh) != len(data.pv_kwh) or not data.load_kwh:
            raise ValueError("Load and PV profiles must have the same non-zero length.")
        if abs(data.interval_hours - 1.0) > 1e-9:
            raise ValueError(
                "The client algorithm expects hourly energy data. "
                "The orchestration layer must aggregate interval data to hourly values first."
            )
        if len(data.import_rates) != len(data.load_kwh):
            raise ValueError("Import tariff series length must match the load profile.")
        if len(data.feed_in_rates) != len(data.load_kwh):
            raise ValueError("Feed-in tariff series length must match the load profile.")
        if len(set(round(float(x), 10) for x in data.import_rates)) != 1:
            raise ValueError(
                "The supplied client algorithm supports one flat retail price per run; "
                "time-of-use rates cannot be silently averaged."
            )
        if len(set(round(float(x), 10) for x in data.feed_in_rates)) != 1:
            raise ValueError("The supplied client algorithm supports one feed-in tariff per run.")
        if data.demand_charge_rate_per_kw_day > 0:
            raise ValueError(
                "Demand charges are not part of the supplied client objective and "
                "cannot be used with the Octave engine."
            )
        vectors = (data.load_kwh, data.pv_kwh, data.import_rates, data.feed_in_rates)
        if any(not math.isfinite(float(x)) for vector in vectors for x in vector):
            raise ValueError("Calculation inputs must contain only finite numeric values.")
        if any(float(x) < 0 for vector in (data.load_kwh, data.pv_kwh) for x in vector):
            raise ValueError("Load and PV values cannot be negative.")
        return float(data.import_rates[0]), float(data.feed_in_rates[0])

    def _invoke(self, data: EngineInput, retail: float, fit: float) -> list[float]:
        executable = self._resolve_executable()
        cli_file = self.source_dir / "run_smart_battery_cli.m"
        algorithm_file = self.source_dir / "smart_battery_optimize.m"
        if not cli_file.exists() or not algorithm_file.exists():
            raise OctaveUnavailable(
                "Octave algorithm source files are missing from octave_source/."
            )

        with tempfile.TemporaryDirectory(prefix="smart-battery-octave-") as tmp:
            tmp_dir = Path(tmp)
            pv_path = tmp_dir / "pv.csv"
            load_path = tmp_dir / "load.csv"
            self._write_vector(pv_path, data.pv_kwh)
            self._write_vector(load_path, data.load_kwh)

            source = self._quote_octave_string(str(self.source_dir.resolve()))
            pv_file = self._quote_octave_string(str(pv_path.resolve()))
            load_file = self._quote_octave_string(str(load_path.resolve()))
            expression = (
                f"addpath('{source}'); "
                f"run_smart_battery_cli('{pv_file}','{load_file}',"
                f"{float(data.pv_size_kw):.17g},"
                f"{float(data.battery_annual_cost_per_kwh):.17g},"
                f"{retail:.17g},"
                f"{fit:.17g},"
                f"{float(data.max_capacity_kwh):.17g},"
                f"{1 if data.pv_profile_is_legacy_base else 0},"
                f"{float(data.battery_installed_cost_per_kwh):.17g});"
            )

            try:
                proc = subprocess.run(
                    [
                        executable,
                        "--quiet",
                        "--no-init-file",
                        "--no-history",
                        "--eval",
                        expression,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    env=None,
                )
            except subprocess.TimeoutExpired as exc:
                raise OctaveExecutionError(
                    f"GNU Octave calculation exceeded the {self.timeout_seconds}s timeout."
                ) from exc
            except OSError as exc:
                raise OctaveUnavailable(f"Could not start GNU Octave: {exc}") from exc

            combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
            if proc.returncode != 0:
                detail = combined.strip()[-2000:]
                raise OctaveExecutionError(
                    "GNU Octave battery algorithm failed."
                    + (f" Octave output: {detail}" if detail else "")
                )

            marker_line = None
            for line in combined.splitlines():
                if self.RESULT_MARKER in line:
                    marker_line = line[line.index(self.RESULT_MARKER) + len(self.RESULT_MARKER) :].strip()

            if not marker_line:
                detail = combined.strip()[-1500:]
                raise OctaveExecutionError(
                    "GNU Octave completed but did not return the expected result marker."
                    + (f" Octave output: {detail}" if detail else "")
                )

            try:
                values = [float(item) for item in marker_line.split(",")]
            except ValueError as exc:
                raise OctaveExecutionError(
                    f"GNU Octave returned a malformed result vector: {marker_line[:500]}"
                ) from exc

            if len(values) < len(self.RESULT_FIELDS):
                raise OctaveExecutionError(
                    f"GNU Octave returned {len(values)} values; "
                    f"{len(self.RESULT_FIELDS)} are required by the v1 API contract."
                )
            if any(not math.isfinite(value) for value in values[: len(self.RESULT_FIELDS)]):
                raise OctaveExecutionError("GNU Octave returned non-finite values.")
            return values

    def calculate(self, data: EngineInput) -> dict:
        retail, fit = self._validate(data)

        if settings.OCTAVE_SERIALIZE_CALLS:
            with type(self)._call_lock:
                values = self._invoke(data, retail, fit)
        else:
            values = self._invoke(data, retail, fit)

        parsed = dict(zip(self.RESULT_FIELDS, values[: len(self.RESULT_FIELDS)]))
        payback = parsed["simple_payback_years"]
        payback_value = None if payback < 0 or payback > 10_000 else round(payback, 2)

        result = {
            "optimal_battery_size_kwh": round(parsed["optimal_battery_size_kwh"], 3),
            "net_annual_payment_aud": round(parsed["net_annual_payment_aud"], 2),
            "baseline_annual_payment_aud": round(parsed["baseline_annual_payment_aud"], 2),
            "estimated_annual_bill_reduction_aud": round(parsed["estimated_annual_bill_reduction_aud"], 2),
            "estimated_annual_bill_reduction_percent": round(parsed["estimated_annual_bill_reduction_percent"], 2),
            "export_to_grid_kwh_year": round(parsed["export_to_grid_kwh_year"], 2),
            "import_from_grid_kwh_year": round(parsed["import_from_grid_kwh_year"], 2),
            "energy_balance_import_minus_export_kwh_year": round(parsed["energy_balance_import_minus_export_kwh_year"], 2),
            "annual_load_kwh": round(parsed["annual_load_kwh"], 2),
            "annual_pv_generation_kwh": round(parsed["annual_pv_generation_kwh"], 2),
            "self_consumption_percent": round(parsed["self_consumption_percent"], 2),
            "baseline_self_consumption_percent": round(parsed["baseline_self_consumption_percent"], 2),
            "battery_annual_payment_rate_aud_per_kwh_year": round(parsed["battery_annual_payment_rate_aud_per_kwh_year"], 3),
            "battery_upfront_cost_aud": round(parsed["battery_upfront_cost_aud"], 2),
            "simple_payback_years": payback_value,
            "average_retail_price_aud_per_kwh": round(parsed["average_retail_price_aud_per_kwh"], 5),
            "average_feed_in_tariff_aud_per_kwh": round(parsed["average_feed_in_tariff_aud_per_kwh"], 5),
            "annual_demand_charge_aud": 0.0,
            "pv_size_kw": round(parsed["pv_size_kw"], 3),
            "optimizer_success": parsed["optimizer_exitflag"] == 1,
            "optimizer_exitflag": int(round(parsed["optimizer_exitflag"])),
            "objective_value": round(parsed["objective_value"], 4),
            "is_demo_result": False,
            "engine": self.version,
            "algorithm_source": "gnu_octave_matlab_compatible_client_algorithm",
            "profile_duration_hours": len(data.load_kwh),
            "profile_is_full_year": len(data.load_kwh) in {8760, 8784},
            "octave_console": {"stdout": "", "stderr": ""},
            "matlab_compatible": {
                "battery_size_kwh": round(parsed["optimal_battery_size_kwh"], 3),
                "net_payment_aud_year": round(parsed["net_annual_payment_aud"], 2),
                "export_kwh_year": round(parsed["export_to_grid_kwh_year"], 2),
                "import_kwh_year": round(parsed["import_from_grid_kwh_year"], 2),
                "losses_legacy_import_minus_export_kwh_year": round(parsed["energy_balance_import_minus_export_kwh_year"], 2),
                "retail_price_aud_per_kwh": round(parsed["average_retail_price_aud_per_kwh"], 5),
                "battery_annual_payment_rate_aud_per_kwh_year": round(parsed["battery_annual_payment_rate_aud_per_kwh_year"], 3),
                "feed_in_tariff_aud_per_kwh": round(parsed["average_feed_in_tariff_aud_per_kwh"], 5),
                "pv_size_kw": round(parsed["pv_size_kw"], 3),
            },
        }
        return result
