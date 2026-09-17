import requests
from django.conf import settings


class MatlabHttpEngine:
    version = "matlab-http-v1"

    def calculate(self, data):
        payload = {
            "load_kwh": data.load_kwh,
            "pv_kwh": data.pv_kwh,
            "interval_hours": data.interval_hours,
            "import_rates": data.import_rates,
            "feed_in_rates": data.feed_in_rates,
            "daily_supply_charge": data.daily_supply_charge,
            "demand_charge_rate_per_kw_day": data.demand_charge_rate_per_kw_day,
            "battery_annual_cost_per_kwh": data.battery_annual_cost_per_kwh,
            "battery_installed_cost_per_kwh": data.battery_installed_cost_per_kwh,
            "max_capacity_kwh": data.max_capacity_kwh,
            "pv_size_kw": data.pv_size_kw,
        }
        response = requests.post(
            settings.MATLAB_ENGINE_URL,
            json=payload,
            timeout=settings.MATLAB_ENGINE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        if "result" not in body or not isinstance(body["result"], dict):
            raise RuntimeError("MATLAB service returned an invalid response contract.")
        return body["result"]
