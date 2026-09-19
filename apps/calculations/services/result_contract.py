from __future__ import annotations

import math
import re

from .errors import CalculationEngineExecutionError
from .interfaces import EngineInput

_REQUIRED_NUMERIC = (
    "optimal_battery_size_kwh",
    "net_annual_payment_aud",
    "baseline_annual_payment_aud",
    "estimated_annual_bill_reduction_aud",
    "estimated_annual_bill_reduction_percent",
    "export_to_grid_kwh_year",
    "import_from_grid_kwh_year",
    "energy_balance_import_minus_export_kwh_year",
    "annual_load_kwh",
    "annual_pv_generation_kwh",
    "self_consumption_percent",
    "baseline_self_consumption_percent",
    "battery_annual_payment_rate_aud_per_kwh_year",
    "battery_upfront_cost_aud",
    "average_retail_price_aud_per_kwh",
    "average_feed_in_tariff_aud_per_kwh",
    "annual_demand_charge_aud",
    "pv_size_kw",
    "objective_value",
    "profile_duration_hours",
)


def _close(actual: float, expected: float, *, absolute: float = 0.05, relative: float = 0.001) -> bool:
    return abs(actual - expected) <= max(absolute, abs(expected) * relative)


def validate_result_contract(result: dict, data: EngineInput) -> dict:
    if not isinstance(result, dict):
        raise CalculationEngineExecutionError("Calculation engine returned a non-object result.")

    missing = [key for key in _REQUIRED_NUMERIC if key not in result]
    if missing:
        raise CalculationEngineExecutionError("Missing result fields: " + ", ".join(sorted(missing)))

    numeric: dict[str, float] = {}
    for key in _REQUIRED_NUMERIC:
        value = result[key]
        if isinstance(value, bool):
            raise CalculationEngineExecutionError(f"Result field {key!r} must be numeric.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise CalculationEngineExecutionError(f"Result field {key!r} is not numeric.") from exc
        if not math.isfinite(number):
            raise CalculationEngineExecutionError(f"Result field {key!r} is not finite.")
        numeric[key] = number

    capacity = numeric["optimal_battery_size_kwh"]
    if capacity < -1e-9 or capacity > 50.000001:
        raise CalculationEngineExecutionError("Optimised battery capacity is outside the legacy 0-50 kWh bound.")

    for key in ("self_consumption_percent", "baseline_self_consumption_percent"):
        if numeric[key] < -1e-6 or numeric[key] > 100.000001:
            raise CalculationEngineExecutionError(f"Result field {key!r} must be between 0 and 100.")

    expected_saving = numeric["baseline_annual_payment_aud"] - numeric["net_annual_payment_aud"]
    if not _close(numeric["estimated_annual_bill_reduction_aud"], expected_saving):
        raise CalculationEngineExecutionError("Bill reduction is inconsistent with baseline minus optimised payment.")

    baseline = numeric["baseline_annual_payment_aud"]
    expected_pct = 0.0 if abs(baseline) <= 1e-12 else expected_saving / baseline * 100.0
    if not _close(numeric["estimated_annual_bill_reduction_percent"], expected_pct, absolute=0.06):
        raise CalculationEngineExecutionError("Bill-reduction percentage is inconsistent.")

    expected_balance = numeric["import_from_grid_kwh_year"] - numeric["export_to_grid_kwh_year"]
    if not _close(numeric["energy_balance_import_minus_export_kwh_year"], expected_balance, relative=1e-6):
        raise CalculationEngineExecutionError("Import/export energy balance is inconsistent.")

    expected_load = sum(float(v) for v in data.load_kwh)
    expected_pv = sum(float(v) for v in data.pv_kwh) * (1742.7 / 1737.0) * (5.0 / 3.0)
    if not _close(numeric["annual_load_kwh"], expected_load, relative=1e-6):
        raise CalculationEngineExecutionError("Annual load does not match the supplied workbook profile.")
    if not _close(numeric["annual_pv_generation_kwh"], expected_pv, relative=1e-6):
        raise CalculationEngineExecutionError("Annual PV does not match the legacy source scaling.")

    fixed_checks = {
        "average_retail_price_aud_per_kwh": 0.3773,
        "average_feed_in_tariff_aud_per_kwh": 0.124,
        "battery_annual_payment_rate_aud_per_kwh_year": 50.0,
        "pv_size_kw": 5.0,
    }
    for key, expected in fixed_checks.items():
        if not _close(numeric[key], expected, absolute=1e-5, relative=1e-8):
            raise CalculationEngineExecutionError(f"Legacy fixed value {key!r} changed unexpectedly.")

    expected_upfront = capacity * float(data.battery_installed_cost_per_kwh)
    tolerance = max(0.10, float(data.battery_installed_cost_per_kwh) * 0.00051 + 0.02)
    if not _close(numeric["battery_upfront_cost_aud"], expected_upfront, absolute=tolerance, relative=1e-6):
        raise CalculationEngineExecutionError("Battery upfront cost is inconsistent.")

    if abs(numeric["annual_demand_charge_aud"]) > 1e-9:
        raise CalculationEngineExecutionError("Legacy source does not support demand charges.")
    if int(round(numeric["profile_duration_hours"])) != len(data.load_kwh):
        raise CalculationEngineExecutionError("Profile duration is inconsistent.")
    if bool(result.get("profile_is_full_year")) != (len(data.load_kwh) in {8760, 8784}):
        raise CalculationEngineExecutionError("Full-year flag is inconsistent.")
    if result.get("optimizer_success") is not True or int(result.get("optimizer_exitflag", 0)) != 1:
        raise CalculationEngineExecutionError("Legacy optimiser did not report convergence.")

    payback = result.get("simple_payback_years")
    if payback is not None:
        payback_value = float(payback)
        if not math.isfinite(payback_value) or payback_value < 0:
            raise CalculationEngineExecutionError("simple_payback_years must be non-negative or null.")

    algorithm_sha256 = str(result.get("algorithm_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", algorithm_sha256):
        raise CalculationEngineExecutionError("algorithm_sha256 is missing or malformed.")

    return result
