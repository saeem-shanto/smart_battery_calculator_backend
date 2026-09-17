import math

import numpy as np
from scipy.optimize import minimize_scalar


class ReferencePythonEngine:
    """
    Transparent Python reference implementation based on the supplied MATLAB
    battery dispatch logic. This is intended for web integration and validation.
    Final scientific acceptance should compare outputs against client-approved
    MATLAB reference scenarios.
    """

    version = "python-port-v1"
    soc_min = 0.10
    soc_max = 0.95
    eff_b = 0.95
    eff_c = 0.96
    eff_d = 0.96

    def _dispatch(self, cap, data):
        load = np.asarray(data.load_kwh, dtype=float)
        pv = np.asarray(data.pv_kwh, dtype=float)
        imports = np.zeros_like(load)
        exports = np.zeros_like(load)

        if cap <= 1e-9:
            net = pv - load
            exports = np.maximum(net, 0)
            imports = np.maximum(-net, 0)
            soc = np.full(len(load), self.soc_min)
            return imports, exports, soc

        soc = np.zeros(len(load), dtype=float)
        soc[0] = self.soc_min
        first = pv[0] - load[0]
        if first >= 0:
            exports[0] = first
        else:
            imports[0] = -first

        for i in range(1, len(load)):
            net = pv[i] - load[i]
            prev = soc[i - 1]
            if net >= 0:
                room = (self.soc_max - prev) * cap
                solar_to_battery = min(net, room / self.eff_c if self.eff_c else 0)
                soc[i] = min(
                    self.soc_max,
                    prev + (solar_to_battery * self.eff_c / cap),
                )
                exports[i] = max(0.0, net - solar_to_battery)
            else:
                deficit = -net
                deliverable = max(
                    0.0,
                    (prev - self.soc_min) * cap * self.eff_b * self.eff_d,
                )
                delivered = min(deficit, deliverable)
                soc[i] = max(
                    self.soc_min,
                    prev
                    - (
                        delivered / (cap * self.eff_b * self.eff_d)
                        if cap
                        else 0
                    ),
                )
                imports[i] = max(0.0, deficit - delivered)

        return imports, exports, soc

    def _demand_charge(self, imports, data, annual_factor):
        rate = float(data.demand_charge_rate_per_kw_day or 0)
        if rate <= 0 or data.interval_hours <= 0:
            return 0.0
        intervals_per_day = max(1, round(24 / data.interval_hours))
        total = 0.0
        for start in range(0, len(imports), intervals_per_day):
            day = imports[start : start + intervals_per_day]
            if len(day) == 0:
                continue
            max_kw = float(np.max(day / data.interval_hours))
            total += max_kw * rate
        return total * annual_factor

    def _cost(self, cap, data):
        imports, exports, _ = self._dispatch(cap, data)
        days = max(1e-9, len(imports) * data.interval_hours / 24)
        annual_factor = 365.0 / days
        import_cost = (
            float(np.dot(imports, np.asarray(data.import_rates))) * annual_factor
        )
        export_credit = (
            float(np.dot(exports, np.asarray(data.feed_in_rates))) * annual_factor
        )
        supply = data.daily_supply_charge * 365
        demand = self._demand_charge(imports, data, annual_factor)
        battery_annual = cap * data.battery_annual_cost_per_kwh
        net = battery_annual + import_cost + supply + demand - export_credit
        return (
            net,
            imports,
            exports,
            annual_factor,
            import_cost,
            export_credit,
            demand,
            battery_annual,
        )

    def calculate(self, data):
        if len(data.load_kwh) != len(data.pv_kwh) or not data.load_kwh:
            raise ValueError("Load and PV profiles must have the same non-zero length.")
        if len(data.import_rates) != len(data.load_kwh):
            raise ValueError("Import tariff series length must match the load profile.")
        if len(data.feed_in_rates) != len(data.load_kwh):
            raise ValueError("Feed-in tariff series length must match the load profile.")

        objective = lambda x: self._cost(float(x), data)[0]
        lo = min(0.001, data.max_capacity_kwh / 1000)
        opt = minimize_scalar(
            objective,
            bounds=(lo, data.max_capacity_kwh),
            method="bounded",
            options={"xatol": 0.05},
        )
        candidate_cap = max(0.0, float(opt.x))
        candidate_cost = objective(candidate_cap)
        no_battery_cost = objective(0.0)
        cap = 0.0 if no_battery_cost <= candidate_cost else candidate_cap

        (
            net,
            imports,
            exports,
            annual_factor,
            import_cost,
            export_credit,
            demand_cost,
            _batt_annual,
        ) = self._cost(cap, data)
        (
            base_net,
            base_imports,
            base_exports,
            _,
            base_import_cost,
            base_export_credit,
            base_demand_cost,
            _,
        ) = self._cost(0.0, data)

        annual_load = sum(data.load_kwh) * annual_factor
        annual_pv = sum(data.pv_kwh) * annual_factor
        annual_import = float(imports.sum()) * annual_factor
        annual_export = float(exports.sum()) * annual_factor
        annual_base_export = float(base_exports.sum()) * annual_factor
        direct_or_stored = max(0.0, annual_pv - annual_export)
        self_consumption = (
            direct_or_stored / annual_pv * 100 if annual_pv > 0 else 0
        )
        baseline_self = (
            (annual_pv - annual_base_export) / annual_pv * 100
            if annual_pv > 0
            else 0
        )

        annual_energy_bill_after = (
            import_cost
            + data.daily_supply_charge * 365
            + demand_cost
            - export_credit
        )
        annual_energy_bill_before = (
            base_import_cost
            + data.daily_supply_charge * 365
            + base_demand_cost
            - base_export_credit
        )
        gross_saving = max(0.0, annual_energy_bill_before - annual_energy_bill_after)
        upfront = cap * data.battery_installed_cost_per_kwh
        payback = upfront / gross_saving if gross_saving > 1e-9 else None
        avg_import = float(np.mean(data.import_rates))
        avg_fit = float(np.mean(data.feed_in_rates))
        legacy_losses = annual_import - annual_export

        result = {
            "optimal_battery_size_kwh": round(cap, 3),
            "net_annual_payment_aud": round(net, 2),
            "baseline_annual_payment_aud": round(base_net, 2),
            "estimated_annual_bill_reduction_aud": round(base_net - net, 2),
            "estimated_annual_bill_reduction_percent": round(
                ((base_net - net) / base_net * 100) if abs(base_net) > 1e-9 else 0,
                2,
            ),
            "export_to_grid_kwh_year": round(annual_export, 2),
            "import_from_grid_kwh_year": round(annual_import, 2),
            "energy_balance_import_minus_export_kwh_year": round(legacy_losses, 2),
            "annual_load_kwh": round(annual_load, 2),
            "annual_pv_generation_kwh": round(annual_pv, 2),
            "self_consumption_percent": round(self_consumption, 2),
            "baseline_self_consumption_percent": round(baseline_self, 2),
            "battery_annual_payment_rate_aud_per_kwh_year": round(
                data.battery_annual_cost_per_kwh, 3
            ),
            "battery_upfront_cost_aud": round(upfront, 2),
            "simple_payback_years": (
                round(payback, 2)
                if payback is not None and math.isfinite(payback)
                else None
            ),
            "average_retail_price_aud_per_kwh": round(avg_import, 5),
            "average_feed_in_tariff_aud_per_kwh": round(avg_fit, 5),
            "annual_demand_charge_aud": round(demand_cost, 2),
            "pv_size_kw": round(data.pv_size_kw, 3),
            "optimizer_success": bool(opt.success),
            "matlab_compatible": {
                "battery_size_kwh": round(cap, 3),
                "net_payment_aud_year": round(net, 2),
                "export_kwh_year": round(annual_export, 2),
                "import_kwh_year": round(annual_import, 2),
                "losses_legacy_import_minus_export_kwh_year": round(legacy_losses, 2),
                "retail_price_aud_per_kwh": round(avg_import, 5),
                "battery_annual_payment_rate_aud_per_kwh_year": round(
                    data.battery_annual_cost_per_kwh, 3
                ),
                "feed_in_tariff_aud_per_kwh": round(avg_fit, 5),
                "pv_size_kw": round(data.pv_size_kw, 3),
            },
        }
        return result
