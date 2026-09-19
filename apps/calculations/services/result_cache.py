from __future__ import annotations


def canonicalize_algorithm_result(result: dict) -> dict:
    """Remove the reporting-only installed-cost fields before caching.

    The unchanged MATLAB/Octave algorithm does not use installed battery cost.
    Keeping a canonical result allows one CSV/result cache to serve repeated
    calculations of the exact same input file while each request can still use
    its own reporting-only installed-cost assumption.
    """
    cached = dict(result)
    cached["battery_upfront_cost_aud"] = 0.0
    cached["simple_payback_years"] = None
    return cached


def apply_reporting_cost(cached_result: dict, battery_installed_cost_per_kwh: float) -> dict:
    result = dict(cached_result)
    capacity = float(result.get("optimal_battery_size_kwh", 0.0))
    installed_cost = float(battery_installed_cost_per_kwh)
    savings = float(result.get("estimated_annual_bill_reduction_aud", 0.0))

    upfront = capacity * installed_cost
    payback = upfront / savings if savings > 1e-12 else None

    result["battery_upfront_cost_aud"] = round(upfront, 2)
    result["simple_payback_years"] = None if payback is None or payback > 10000 else round(payback, 2)
    return result
