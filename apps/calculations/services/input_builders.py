from __future__ import annotations

from .interfaces import EngineInput


LEGACY_RETAIL_RATE = 0.3773
LEGACY_FEED_IN_RATE = 0.124
LEGACY_BATTERY_ANNUAL_RATE = 50.0
LEGACY_MAX_BATTERY_KWH = 50.0
LEGACY_PV_SIZE_KW = 5.0


def build_client_workbook_engine_input(workbook, attrs: dict) -> tuple[EngineInput, list[str], list[str]]:
    """Map the client workbook to the immutable legacy MATLAB contract."""
    data = EngineInput(
        load_kwh=[float(x) for x in workbook.load_profile],
        pv_kwh=[float(x) for x in workbook.pv_base_profile],
        interval_hours=1.0,
        battery_installed_cost_per_kwh=float(attrs["battery_installed_cost_per_kwh"]),
    )

    assumptions = [
        "The original client MATLAB files are executed unchanged under GNU Octave.",
        "Column 1 is the legacy/base PV profile and column 2 is household load; each accepted row is one hour.",
        "The legacy source fixes PV size at 5 kW, battery annual payment rate at AUD 50/kWh/year, retail price at AUD 0.3773/kWh, feed-in tariff at AUD 0.124/kWh, and the battery search range at 0-50 kWh.",
        "The original natpaymenttrail.m scaling (1742.7/1737) x (5/3) is applied by the unchanged MATLAB source.",
        "Installed battery cost is a Django reporting assumption used only for simple payback; it does not modify the legacy optimisation objective.",
    ]
    return data, assumptions, list(workbook.warnings or [])


def build_direct_engine_input(attrs: dict) -> EngineInput:
    """Diagnostic-only builder that still executes the immutable legacy source."""
    return EngineInput(
        load_kwh=[float(x) for x in attrs["load_profile"]],
        pv_kwh=[float(x) for x in attrs["pv_profile"]],
        interval_hours=1.0,
        battery_installed_cost_per_kwh=float(attrs.get("battery_installed_cost_per_kwh", 1000.0)),
    )
