"""Django-only adapter for the client-supplied batt_cal_v1.m.

The user's uploaded source is preserved byte-for-byte in matlab_source_v1/.
Parameters are inserted into a temporary copy with checks against exact source
patterns. No financial or energy flow calculation runs in Next.js.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from django.conf import settings

from .errors import CalculationEngineExecutionError, CalculationEngineUnavailable

RETAIL_DEFAULT = (0.33, 0.165, 0.165, 0.165, 0.165, 0.165, 0.165, 0.165, 0.165, 0.33, 0.33, 0.33,
                  0.22, 0.22, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33)
FEED_DEFAULT = (0.03, 0.03, 0.03, 0.03, 0.03, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.02, 0.02, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03, 0.03)
PV_CORRECTION = 1742.7 / 1737.0


@dataclass(frozen=True)
class UpdatedModelSettings:
    battery_capacity_kwh: float = 15
    pv_capacity_kw: float = 6
    interest_rate_percent: float = 2
    installation_cost_aud: float = 8000
    loan_period_years: int = 10
    daily_supply_charge_aud: float = 1.01
    retail_tariff_24h: tuple[float, ...] = RETAIL_DEFAULT
    feed_in_tariff_24h: tuple[float, ...] = FEED_DEFAULT


def _check_number(name: str, value: float, low: float, high: float) -> None:
    if isinstance(value, bool) or not math.isfinite(float(value)) or not low <= float(value) <= high:
        raise ValueError(f"{name} must be finite and between {low} and {high}.")


def validate_settings(s: UpdatedModelSettings) -> None:
    for name, value, low, high in (
        ("battery_capacity_kwh", s.battery_capacity_kwh, 1, 50),
        ("pv_capacity_kw", s.pv_capacity_kw, 0.5, 30),
        ("interest_rate_percent", s.interest_rate_percent, 0, 20),
        ("installation_cost_aud", s.installation_cost_aud, 0, 100000),
        ("daily_supply_charge_aud", s.daily_supply_charge_aud, 0, 5),
    ):
        _check_number(name, value, low, high)
    if isinstance(s.loan_period_years, bool) or not isinstance(s.loan_period_years, int) or not 1 <= s.loan_period_years <= 30:
        raise ValueError("loan_period_years must be an integer between 1 and 30.")
    for name, values in (("retail_tariff_24h", s.retail_tariff_24h), ("feed_in_tariff_24h", s.feed_in_tariff_24h)):
        if len(values) != 24:
            raise ValueError(f"{name} must contain exactly 24 values.")
        for value in values:
            _check_number(name, value, 0, 5)


def _fmt(value: float) -> str:
    return format(float(value), ".15g")


def _replace_once(source: str, pattern: str, replacement: str) -> str:
    replaced, count = re.subn(pattern, lambda _m: replacement, source, count=1, flags=re.MULTILINE)
    if count != 1:
        raise CalculationEngineExecutionError(f"Client source incompatible with safe parameter insertion: {pattern!r}")
    return replaced


def render_runtime_script(source: str, params: UpdatedModelSettings, *, daily_average_kwh: float) -> str:
    """Substitute source constants in isolated runtime copy; keep dispatch equations unchanged.

    The user's reference file must retain the exact recognizable assignments.
    The only deliberate numerical fix is the 0% financing edge case.
    """
    validate_settings(params)
    _check_number("daily_average_kwh", daily_average_kwh, 0.000000001, 1_000_000)
    replacements = (
        (r"^x\s*=\s*15\s*;[^\n]*", f"x={_fmt(params.battery_capacity_kwh)}; % user-selected battery capacity"),
        (r"^daily_avg\s*=\s*14\.2766\s*;[^\n]*", f"daily_avg={_fmt(daily_average_kwh)}; % calculated on backend from load data"),
        (r"^cap_pv\s*=\s*6\s*;[^\n]*", f"cap_pv={_fmt(params.pv_capacity_kw)}; % selected PV capacity"),
        (r"^i\s*=\s*0\.02\s*;[^\n]*", f"i={_fmt(params.interest_rate_percent / 100)}; % fraction, not percent"),
        (r"^IC\s*=\s*8000\s*;[^\n]*", f"IC={_fmt(params.installation_cost_aud)}; % total financed installation cost"),
        (r"^lspan\s*=\s*10\s*;[^\n]*", f"lspan={params.loan_period_years}; % loan duration"),
        (r"^dc\s*=\s*101/100\s*;[^\n]*", f"dc={_fmt(params.daily_supply_charge_aud)}; % per-day supply charge"),
    )
    for pattern, replacement in replacements:
        source = _replace_once(source, pattern, replacement)
    source = _replace_once(source, r"(?s)^rp_tou\s*=\s*\[[^]]*\];[^\n]*", "rp_tou=[" + ";".join(map(_fmt, params.retail_tariff_24h)) + "]; % retailer hourly prices")
    source = _replace_once(source, r"(?s)^fit_tou\s*=\s*\[[^]]*\];[^\n]*", "fit_tou=[" + ";".join(map(_fmt, params.feed_in_tariff_24h)) + "]; % retailer hourly export tariffs")
    # Without this guard, the original CRF expression is 0/0 at i=0.
    source = _replace_once(source,
                           r"^crf\s*=\s*\(i\*\(1\+i\)\^lspan\)/\(\(\(1\+i\)\^lspan\)-1\);[^\n]*",
                           "if i==0; crf=1/lspan; else; crf=(i*(1+i)^lspan)/(((1+i)^lspan)-1); end")
    return source


def parse_runtime_output(raw: bytes) -> tuple[float, ...]:
    try:
        rows = [row for row in csv.reader(io.StringIO(raw.decode("utf-8-sig"))) if row]
        values = tuple(float(item) for item in rows[-1])
    except (ValueError, UnicodeError, IndexError) as exc:
        raise CalculationEngineExecutionError("Updated model produced an unreadable CSV.") from exc
    if len(values) != 7 or not all(math.isfinite(x) for x in values):
        raise CalculationEngineExecutionError("Updated model must produce exactly 7 finite values.")
    return values


class UpdatedBatteryEngine:
    version = "gnu-octave-batt-cal-v1"
    output_filename = "Results_RPAtrail400.csv"

    def __init__(self):
        self.source_path = Path(settings.BASE_DIR) / "matlab_source_v1" / "batt_cal_v1.m"
        self.bridge_dir = Path(settings.BASE_DIR) / "octave_bridge"
        self.executable = settings.OCTAVE_EXECUTABLE
        self.timeout_seconds = settings.OCTAVE_TIMEOUT_SECONDS

    def calculate(self, pv_base: Sequence[float], load: Sequence[float], params: UpdatedModelSettings) -> tuple[dict, bytes, int]:
        validate_settings(params)
        if len(pv_base) != 8760 or len(load) != 8760:
            raise ValueError("The updated model requires exactly 8,760 hourly PV and load observations.")
        if any(not math.isfinite(float(a)) or float(a) < 0 for a in (*pv_base, *load)):
            raise ValueError("PV and load observations must be finite and non-negative.")
        annual_load = sum(load)
        if annual_load <= 0:
            raise ValueError("The 24-hour consumption table must contain a non-zero load.")
        if not self.source_path.exists() or not (self.bridge_dir / "xlsread.m").exists():
            raise CalculationEngineUnavailable("Updated client MATLAB source or xlsread adapter is missing.")
        executable = shutil.which(self.executable)
        if not executable:
            raise CalculationEngineUnavailable("GNU Octave is not installed or is missing from PATH.")
        original = self.source_path.read_bytes()
        source_hash = hashlib.sha256(original).hexdigest()
        runtime_source = render_runtime_script(original.decode("utf-8-sig"), params, daily_average_kwh=annual_load / 365)

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="n01-batt-cal-v1-") as directory:
            directory_path = Path(directory)
            (directory_path / "batt_cal_v1_web.m").write_text(runtime_source, encoding="utf-8")
            with (directory_path / "Vanikavipuldata.xls").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerows(zip(pv_base, load))
            octave_dir = str(directory_path).replace("'", "''")
            octave_bridge = str(self.bridge_dir.resolve()).replace("'", "''")
            expression = f"addpath('{octave_bridge}'); cd('{octave_dir}'); batt_cal_v1_web;"
            env = dict(os.environ, HOME=str(directory_path), OCTAVE_HISTFILE=os.devnull,
                       OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
            try:
                process = subprocess.run([executable, "--quiet", "--no-init-file", "--no-history", "--eval", expression],
                                         cwd=directory_path, env=env, text=True, capture_output=True,
                                         timeout=self.timeout_seconds, check=False)
            except subprocess.TimeoutExpired as exc:
                raise CalculationEngineExecutionError("Updated MATLAB calculation timed out.") from exc
            except OSError as exc:
                raise CalculationEngineUnavailable("Could not launch GNU Octave.") from exc
            if process.returncode:
                # Never include the API token or user input in a surfaced traceback.
                raise CalculationEngineExecutionError("GNU Octave failed to execute batt_cal_v1: " + (process.stderr or process.stdout)[-1200:])
            output_path = directory_path / self.output_filename
            if not output_path.exists():
                raise CalculationEngineExecutionError("Updated MATLAB code did not produce Results_RPAtrail400.csv.")
            raw = output_path.read_bytes()
        elapsed = max(0, round((time.perf_counter() - started) * 1000))
        capacity, net_payment, export, imported, model_losses, annual_installment, cap_pv = parse_runtime_output(raw)
        if abs(capacity - params.battery_capacity_kwh) > 0.0001 or abs(cap_pv - params.pv_capacity_kw) > 0.0001:
            raise CalculationEngineExecutionError("Updated model output does not match the selected system sizes.")
        # The generated profile's PV column is scaled for the legacy model's 5-kW baseline.
        # The new client script uses cap_pv/3, so this is the physical selected-capacity PV.
        pv = [float(v) * PV_CORRECTION * (params.pv_capacity_kw / 3) for v in pv_base]
        annual_pv = sum(pv)
        baseline_export_hourly = [min(5.0, max(a-b, 0)) for a, b in zip(pv, load)]
        baseline_import_hourly = [max(b-a, 0) for a, b in zip(pv, load)]
        baseline_export = sum(baseline_export_hourly)
        baseline_import = sum(baseline_import_hourly)
        retail = params.retail_tariff_24h
        fit = params.feed_in_tariff_24h
        baseline_operation = sum(v * retail[h%24] for h,v in enumerate(baseline_import_hourly)) - sum(v * fit[h%24] for h,v in enumerate(baseline_export_hourly)) + params.daily_supply_charge_aud * 365
        baseline_net = baseline_operation
        savings = baseline_net - net_payment  # includes financing payment in the new-model scenario
        annual_operating_savings = baseline_operation - (net_payment - annual_installment)
        simple_payback = (params.installation_cost_aud / annual_operating_savings if annual_operating_savings > 1e-9 else None)
        self_consumption = 100 * (1-export/annual_pv) if annual_pv else 0
        baseline_self_consumption = 100 * (1-baseline_export/annual_pv) if annual_pv else 0
        result = {
            "optimal_battery_size_kwh": round(capacity, 3), # compatibility alias only, NOT an optimum
            "battery_capacity_kwh": round(capacity, 3),
            "calculation_mode": "selected_capacity",
            "net_annual_payment_aud": round(net_payment, 2),
            "baseline_annual_payment_aud": round(baseline_net, 2),
            "estimated_annual_bill_reduction_aud": round(savings, 2),
            "estimated_annual_bill_reduction_percent": round(savings/baseline_net*100 if abs(baseline_net)>1e-9 else 0, 2),
            "annual_operating_savings_before_financing_aud": round(annual_operating_savings, 2),
            "annual_installment_aud": round(annual_installment, 2),
            "export_to_grid_kwh_year": round(export, 2),
            "import_from_grid_kwh_year": round(imported, 2),
            "energy_balance_import_minus_export_kwh_year": round(imported-export, 2),
            "model_losses_kwh_year": round(model_losses, 2),
            "annual_load_kwh": round(annual_load, 2),
            "annual_pv_generation_kwh": round(annual_pv, 2),
            "self_consumption_percent": round(max(0,min(100,self_consumption)), 2),
            "baseline_self_consumption_percent": round(max(0,min(100,baseline_self_consumption)), 2),
            "battery_annual_payment_rate_aud_per_kwh_year": round(annual_installment/capacity, 3),
            "battery_upfront_cost_aud": round(params.installation_cost_aud,2),
            "simple_payback_years": None if simple_payback is None else round(simple_payback,2),
            "average_retail_price_aud_per_kwh": round(sum(retail)/24, 5),
            "average_feed_in_tariff_aud_per_kwh": round(sum(fit)/24, 5),
            "annual_demand_charge_aud": 0.0,
            "pv_size_kw": round(cap_pv,3),
            "optimizer_success": False, "optimizer_exitflag": 0,
            "objective_value": round(net_payment,4),
            "engine": self.version,
            "algorithm_source": "client_batt_cal_v1_parameterised_runtime_copy",
            "algorithm_sha256": source_hash,
            "profile_duration_hours": 8760, "profile_is_full_year": True,
        }
        return result, raw, elapsed
