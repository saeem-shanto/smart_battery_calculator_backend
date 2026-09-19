from dataclasses import dataclass


@dataclass
class EngineInput:
    load_kwh: list[float]
    pv_kwh: list[float]
    interval_hours: float = 1.0
    battery_installed_cost_per_kwh: float = 1000.0
    # These values are fixed by the immutable client MATLAB source. They remain
    # explicit in the contract so result validation can prove source fidelity.
    import_rate_per_kwh: float = 0.3773
    feed_in_rate_per_kwh: float = 0.124
    battery_annual_cost_per_kwh: float = 50.0
    max_capacity_kwh: float = 50.0
    pv_size_kw: float = 5.0
    pv_profile_is_legacy_base: bool = True
