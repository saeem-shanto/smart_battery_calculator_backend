from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from django.conf import settings

from .errors import CalculationEngineExecutionError, CalculationEngineUnavailable
from .interfaces import EngineInput


class OctaveUnavailable(CalculationEngineUnavailable):
    """Raised when GNU Octave / octave-cli is not installed or accessible."""


class OctaveExecutionError(CalculationEngineExecutionError):
    """Raised when the unchanged client MATLAB source fails inside GNU Octave."""


class OctaveEngine:
    """Execute the client's original MATLAB files unchanged under GNU Octave.

    The immutable source files are:
      - battrail.m
      - natpaymenttrail.m
      - rpresults.m

    natpaymenttrail.m expects a file named ``Vanikavipuldata.xls`` and writes
    ``Results_RPAtrail400.csv``. Django preserves the user's original uploaded
    file bytes/filename in PostgreSQL. For execution only, the already-validated
    first two numeric columns are written into a private temporary compatibility
    file with the exact legacy filename expected by natpaymenttrail.m. The
    compatibility ``xlsread.m`` shim lives outside ``matlab_source`` so the
    client MATLAB source is never renamed or edited.
    """

    version = "gnu-octave-original-matlab-v1"
    _call_lock = threading.Lock()

    LEGACY_INPUT_FILENAME = "Vanikavipuldata.xls"
    LEGACY_OUTPUT_FILENAME = "Results_RPAtrail400.csv"
    SOURCE_FILENAMES = ("battrail.m", "natpaymenttrail.m", "rpresults.m")

    # Fixed by the original source code. Do not expose these as configurable
    # optimisation inputs unless the client supplies a revised MATLAB version.
    PV_SIZE_KW = 5.0
    BATTERY_ANNUAL_RATE = 50.0
    RETAIL_RATE = 0.3773
    FEED_IN_RATE = 0.124
    MAX_BATTERY_KWH = 50.0

    def __init__(self) -> None:
        self.executable = settings.OCTAVE_EXECUTABLE
        self.timeout_seconds = settings.OCTAVE_TIMEOUT_SECONDS
        self.source_dir = Path(settings.BASE_DIR) / "matlab_source"
        self.bridge_dir = Path(settings.BASE_DIR) / "octave_bridge"

    @staticmethod
    def _quote_octave_string(value: str) -> str:
        return value.replace("'", "''")

    def _source_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for filename in self.SOURCE_FILENAMES:
            path = self.source_dir / filename
            if path.exists():
                hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hashes

    def _algorithm_sha256(self) -> str | None:
        if not all((self.source_dir / name).exists() for name in self.SOURCE_FILENAMES):
            return None
        digest = hashlib.sha256()
        for filename in self.SOURCE_FILENAMES:
            digest.update(filename.encode("utf-8"))
            digest.update(b"\0")
            digest.update((self.source_dir / filename).read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def _resolve_executable(self) -> str:
        path = shutil.which(self.executable)
        if not path:
            raise OctaveUnavailable(
                f"GNU Octave executable {self.executable!r} was not found."
            )
        return path

    def status(self) -> dict[str, Any]:
        executable_path = shutil.which(self.executable)
        source_ready = all((self.source_dir / name).exists() for name in self.SOURCE_FILENAMES)
        bridge_ready = (self.bridge_dir / "xlsread.m").exists()
        error = None
        version = None

        if executable_path:
            try:
                proc = subprocess.run(
                    [executable_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                lines = (proc.stdout or proc.stderr).splitlines()
                version = lines[0].strip() if lines else None
                if proc.returncode != 0:
                    error = (proc.stderr or proc.stdout).strip()[-1000:]
            except Exception as exc:  # pragma: no cover - process/platform specific
                error = f"{type(exc).__name__}: {exc}"
        else:
            error = f"{self.executable!r} was not found on PATH."

        return {
            "engine": self.version,
            "runtime_ready": bool(executable_path and source_ready and bridge_ready and not error),
            "octave_executable": self.executable,
            "octave_path": executable_path,
            "octave_version": version,
            "algorithm_source_present": source_ready,
            "bridge_present": bridge_ready,
            "algorithm_files": self._source_hashes(),
            "algorithm_sha256": self._algorithm_sha256(),
            "legacy_input_filename": self.LEGACY_INPUT_FILENAME,
            "legacy_output_filename": self.LEGACY_OUTPUT_FILENAME,
            "serialize_calls": bool(settings.OCTAVE_SERIALIZE_CALLS),
            "timeout_seconds": self.timeout_seconds,
            "error": error,
        }

    @staticmethod
    def _validate(data: EngineInput) -> None:
        if not data.pv_profile_is_legacy_base:
            raise ValueError("The immutable legacy MATLAB workflow requires the client base-PV profile format.")
        if abs(float(data.interval_hours) - 1.0) > 1e-9:
            raise ValueError("The original MATLAB source assumes one-hour rows.")
        if not data.load_kwh or len(data.load_kwh) != len(data.pv_kwh):
            raise ValueError("PV and load profiles must have the same non-zero length.")
        if len(data.load_kwh) > 100_000:
            raise ValueError("The input profile exceeds the supported row limit.")
        for vector_name, vector in (("PV", data.pv_kwh), ("load", data.load_kwh)):
            for value in vector:
                number = float(value)
                if not math.isfinite(number) or number < 0:
                    raise ValueError(f"{vector_name} values must be finite and non-negative.")
        if not math.isfinite(float(data.battery_installed_cost_per_kwh)) or float(data.battery_installed_cost_per_kwh) < 0:
            raise ValueError("battery_installed_cost_per_kwh must be finite and non-negative.")

        expected = {
            "import_rate_per_kwh": (float(data.import_rate_per_kwh), OctaveEngine.RETAIL_RATE),
            "feed_in_rate_per_kwh": (float(data.feed_in_rate_per_kwh), OctaveEngine.FEED_IN_RATE),
            "battery_annual_cost_per_kwh": (float(data.battery_annual_cost_per_kwh), OctaveEngine.BATTERY_ANNUAL_RATE),
            "max_capacity_kwh": (float(data.max_capacity_kwh), OctaveEngine.MAX_BATTERY_KWH),
            "pv_size_kw": (float(data.pv_size_kw), OctaveEngine.PV_SIZE_KW),
        }
        changed = [name for name, (actual, fixed) in expected.items() if abs(actual - fixed) > 1e-9]
        if changed:
            raise ValueError(
                "The original MATLAB source fixes these values and cannot accept overrides: "
                + ", ".join(changed)
                + "."
            )

    @staticmethod
    def _write_legacy_runtime_input(path: Path, pv: list[float], load: list[float]) -> None:
        # The private compatibility file is numeric-only and is not the persisted
        # user upload. It exists solely so unchanged natpaymenttrail.m can call
        # xlsread('Vanikavipuldata.xls') under lightweight GNU Octave.
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            for pv_value, load_value in zip(pv, load):
                writer.writerow([format(float(pv_value), ".17g"), format(float(load_value), ".17g")])

    @staticmethod
    def _parse_legacy_csv(raw_csv: bytes) -> list[float]:
        try:
            text = raw_csv.decode("utf-8-sig")
            rows = [row for row in csv.reader(io.StringIO(text)) if row]
            if not rows:
                raise ValueError("empty CSV")
            values = [float(item) for item in rows[-1]]
        except Exception as exc:
            raise OctaveExecutionError("The legacy MATLAB CSV result could not be parsed.") from exc
        if len(values) < 10:
            raise OctaveExecutionError(
                f"The legacy MATLAB CSV contains {len(values)} columns; at least 10 are expected."
            )
        if any(not math.isfinite(v) for v in values[:10]):
            raise OctaveExecutionError("The legacy MATLAB CSV contains non-finite values.")
        return values

    def _invoke(self, data: EngineInput) -> tuple[list[float], bytes, str]:
        executable = self._resolve_executable()
        if not all((self.source_dir / name).exists() for name in self.SOURCE_FILENAMES):
            raise OctaveUnavailable("One or more immutable client MATLAB source files are missing.")
        if not (self.bridge_dir / "xlsread.m").exists():
            raise OctaveUnavailable("The GNU Octave xlsread compatibility bridge is missing.")

        with tempfile.TemporaryDirectory(prefix="smart-battery-legacy-") as tmp:
            tmp_dir = Path(tmp)
            runtime_input = tmp_dir / self.LEGACY_INPUT_FILENAME
            runtime_output = tmp_dir / self.LEGACY_OUTPUT_FILENAME
            self._write_legacy_runtime_input(runtime_input, data.pv_kwh, data.load_kwh)

            source = self._quote_octave_string(str(self.source_dir.resolve()))
            bridge = self._quote_octave_string(str(self.bridge_dir.resolve()))
            workdir = self._quote_octave_string(str(tmp_dir.resolve()))
            expression = (
                f"addpath('{bridge}'); "
                f"addpath('{source}'); "
                f"cd('{workdir}'); "
                "natpaymenttrail;"
            )

            process_env = os.environ.copy()
            process_env.update(
                {
                    "OMP_NUM_THREADS": "1",
                    "OPENBLAS_NUM_THREADS": "1",
                    "MKL_NUM_THREADS": "1",
                    "OCTAVE_HISTFILE": os.devnull,
                    "HOME": str(tmp_dir),
                }
            )

            try:
                proc = subprocess.run(
                    [executable, "--quiet", "--no-init-file", "--no-history", "--eval", expression],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    env=process_env,
                )
            except subprocess.TimeoutExpired as exc:
                raise OctaveExecutionError(
                    f"GNU Octave calculation exceeded the {self.timeout_seconds}s timeout."
                ) from exc
            except OSError as exc:
                raise OctaveUnavailable(f"Could not start GNU Octave: {exc}") from exc

            console = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
            if proc.returncode != 0:
                raise OctaveExecutionError(
                    "GNU Octave failed while executing the unchanged client MATLAB source. "
                    + console[-1800:]
                )
            if not runtime_output.exists():
                raise OctaveExecutionError(
                    "The unchanged MATLAB source completed without producing Results_RPAtrail400.csv."
                )

            raw_csv = runtime_output.read_bytes()
            values = self._parse_legacy_csv(raw_csv)
            return values, raw_csv, console

    def calculate(self, data: EngineInput) -> tuple[dict, dict[str, bytes]]:
        self._validate(data)
        if settings.OCTAVE_SERIALIZE_CALLS:
            with type(self)._call_lock:
                values, raw_csv, _console = self._invoke(data)
        else:
            values, raw_csv, _console = self._invoke(data)

        # natpaymenttrail.m writes [x yy xx cap_pv]. yy contains seven values,
        # so the raw legacy CSV has 10 columns. Column 9 duplicates xx/Ab and
        # column 10 is cap_pv. We preserve the raw CSV exactly and map it here.
        capacity = float(values[0])
        net_payment = float(values[1])
        export_kwh = float(values[2])
        import_kwh = float(values[3])
        losses = float(values[4])
        retail = float(values[5])
        annual_rate = float(values[6])
        fit = float(values[7])
        pv_size = float(values[9])

        pv_scaled = [
            float(v) * (1742.7 / 1737.0) * (self.PV_SIZE_KW / 3.0)
            for v in data.pv_kwh
        ]
        load = [float(v) for v in data.load_kwh]
        baseline_export = sum(max(pv - demand, 0.0) for pv, demand in zip(pv_scaled, load))
        baseline_import = sum(max(demand - pv, 0.0) for pv, demand in zip(pv_scaled, load))
        baseline_net = baseline_import * retail - baseline_export * fit
        savings = baseline_net - net_payment
        savings_pct = (savings / baseline_net * 100.0) if abs(baseline_net) > 1e-12 else 0.0

        installed_cost = float(data.battery_installed_cost_per_kwh)
        upfront_cost = capacity * installed_cost
        payback = upfront_cost / savings if savings > 1e-12 else None
        annual_pv = sum(pv_scaled)
        annual_load = sum(load)
        self_consumption = ((annual_pv - export_kwh) / annual_pv * 100.0) if annual_pv > 1e-12 else 0.0
        baseline_self = ((annual_pv - baseline_export) / annual_pv * 100.0) if annual_pv > 1e-12 else 0.0

        result = {
            "optimal_battery_size_kwh": round(capacity, 3),
            "net_annual_payment_aud": round(net_payment, 2),
            "baseline_annual_payment_aud": round(baseline_net, 2),
            "estimated_annual_bill_reduction_aud": round(savings, 2),
            "estimated_annual_bill_reduction_percent": round(savings_pct, 2),
            "export_to_grid_kwh_year": round(export_kwh, 2),
            "import_from_grid_kwh_year": round(import_kwh, 2),
            "energy_balance_import_minus_export_kwh_year": round(losses, 2),
            "annual_load_kwh": round(annual_load, 2),
            "annual_pv_generation_kwh": round(annual_pv, 2),
            "self_consumption_percent": round(max(0.0, min(100.0, self_consumption)), 2),
            "baseline_self_consumption_percent": round(max(0.0, min(100.0, baseline_self)), 2),
            "battery_annual_payment_rate_aud_per_kwh_year": round(annual_rate, 3),
            "battery_upfront_cost_aud": round(upfront_cost, 2),
            "simple_payback_years": None if payback is None or payback > 10000 else round(payback, 2),
            "average_retail_price_aud_per_kwh": round(retail, 5),
            "average_feed_in_tariff_aud_per_kwh": round(fit, 5),
            "annual_demand_charge_aud": 0.0,
            "pv_size_kw": round(pv_size, 3),
            "optimizer_success": True,
            "optimizer_exitflag": 1,
            "objective_value": round(net_payment, 4),
            "engine": self.version,
            "algorithm_source": "unchanged_client_matlab_files_v1",
            "algorithm_sha256": self._algorithm_sha256(),
            "profile_duration_hours": len(load),
            "profile_is_full_year": len(load) in {8760, 8784},
        }
        return result, {self.LEGACY_OUTPUT_FILENAME: raw_csv}
