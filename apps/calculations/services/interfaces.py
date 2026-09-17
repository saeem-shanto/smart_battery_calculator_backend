from dataclasses import dataclass
from typing import Protocol

@dataclass
class EngineInput:
    load_kwh: list[float]
    pv_kwh: list[float]
    interval_hours: float
    import_rates: list[float]
    feed_in_rates: list[float]
    daily_supply_charge: float
    demand_charge_rate_per_kw_day: float
    battery_annual_cost_per_kwh: float
    battery_installed_cost_per_kwh: float
    max_capacity_kwh: float
    pv_size_kw: float

class CalculationEngine(Protocol):
    version: str
    def calculate(self, data: EngineInput) -> dict: ...
