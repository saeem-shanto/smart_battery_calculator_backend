from django.test import TestCase

from .services.interfaces import EngineInput
from .services.reference_engine import ReferencePythonEngine


class ReferenceEngineTests(TestCase):
    def test_engine_returns_bounded_capacity_and_compatibility_shape(self):
        load = [0.6] * 24
        pv = [0.0] * 7 + [1.1] * 10 + [0.0] * 7
        data = EngineInput(
            load_kwh=load,
            pv_kwh=pv,
            interval_hours=1.0,
            import_rates=[0.40] * 24,
            feed_in_rates=[0.08] * 24,
            daily_supply_charge=1.0,
            demand_charge_rate_per_kw_day=0,
            battery_annual_cost_per_kwh=50,
            battery_installed_cost_per_kwh=1000,
            max_capacity_kwh=20,
            pv_size_kw=6.6,
        )
        result = ReferencePythonEngine().calculate(data)
        self.assertGreaterEqual(result["optimal_battery_size_kwh"], 0)
        self.assertLessEqual(result["optimal_battery_size_kwh"], 20)
        self.assertEqual(len(result["matlab_compatible"]), 9)
