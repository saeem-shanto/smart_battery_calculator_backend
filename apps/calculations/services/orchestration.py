from __future__ import annotations

from dateutil import parser as dtparser
from rest_framework.exceptions import ValidationError

from apps.profiles.models import ProfileUpload
from apps.tariffs.models import TariffPlan

from .interfaces import EngineInput
from .profiles import ensure_energy, representative_load, representative_pv, timestamps_for_length


def _aggregate_hourly(values: list[float], interval_minutes: int) -> list[float]:
    """Aggregate interval energy to hourly energy without inventing interpolation."""
    if interval_minutes == 60:
        return [float(v) for v in values]
    if interval_minutes <= 0 or 60 % interval_minutes != 0:
        raise ValidationError(
            {"upload_token": f"The client MATLAB algorithm requires hourly data. "
                             f"{interval_minutes}-minute intervals cannot be losslessly grouped into hours."}
        )
    group = 60 // interval_minutes
    usable = len(values) - (len(values) % group)
    if usable == 0:
        raise ValidationError({"upload_token": "Not enough interval data to form one hourly value."})
    return [sum(values[i : i + group]) for i in range(0, usable, group)]


def _hourly_timestamps(raw_ts: list[str], original_interval: int, count: int):
    if raw_ts:
        parsed = []
        for value in raw_ts:
            try:
                parsed.append(dtparser.parse(value))
            except Exception:
                parsed = []
                break
        if parsed:
            if original_interval == 60:
                return parsed[:count]
            if 60 % original_interval == 0:
                group = 60 // original_interval
                return [parsed[i] for i in range(0, min(len(parsed), count * group), group)][:count]
    return timestamps_for_length(count, 60)


def _flat_tariff_rates(attrs, timestamps, n):
    """
    Resolve a tariff without changing the client algorithm.

    The supplied MATLAB objective has one scalar retail price and one scalar FIT.
    TOU and demand-charge tariffs are rejected instead of being silently averaged.
    """
    if attrs.get("tariff_id"):
        try:
            plan = TariffPlan.objects.get(id=attrs["tariff_id"], is_active=True)
        except TariffPlan.DoesNotExist as exc:
            raise ValidationError({"tariff_id": "Tariff not found or inactive."}) from exc

        if plan.kind != TariffPlan.Kind.FLAT:
            raise ValidationError(
                {"tariff_id": "The supplied client MATLAB algorithm currently supports flat retail tariffs only. "
                              "A TOU tariff cannot be averaged without changing the algorithm."}
            )
        if plan.flat_import_rate is None:
            raise ValidationError({"tariff_id": "Flat tariff is missing its import rate."})
        if float(plan.demand_charge_rate_per_kw_day or 0) > 0:
            raise ValidationError(
                {"tariff_id": "Demand charges are not part of the supplied client MATLAB objective."}
            )
        return (
            [float(plan.flat_import_rate)] * n,
            [float(plan.feed_in_rate)] * n,
            float(plan.daily_supply_charge),
            0.0,
            f"{plan.provider} {plan.name}".strip(),
        )

    demand = float(attrs.get("custom_demand_charge_rate_per_kw_day") or 0)
    if demand > 0:
        raise ValidationError(
            {"custom_demand_charge_rate_per_kw_day": "Demand charges are not part of the supplied client MATLAB objective."}
        )
    return (
        [float(attrs["custom_import_rate"])] * n,
        [float(attrs.get("custom_feed_in_rate") or 0)] * n,
        float(attrs.get("custom_daily_supply_charge") or 0),
        0.0,
        "Custom flat tariff",
    )


def build_engine_input(attrs):
    assumptions: list[str] = []
    warnings: list[str] = []
    legacy_base_profile = False
    mode = attrs["source_mode"]

    if mode == "simplified":
        # Representative functions already generate hourly energy for 365 days.
        interval = 60
        load = representative_load(
            attrs["daily_consumption_kwh"],
            attrs.get("occupants", 2),
            attrs.get("afternoon_occupancy", False),
        )
        pv = representative_pv(attrs["pv_size_kw"])
        timestamps = timestamps_for_length(len(load), interval)
        assumptions += [
            "Household demand uses a transparent representative hourly profile scaled to the entered daily consumption.",
            "PV generation uses a representative annual solar shape and is not a postcode-specific weather simulation.",
            "The generated profiles are passed to the client MATLAB battery optimisation algorithm.",
        ]
    else:
        try:
            upload = ProfileUpload.objects.get(id=attrs["upload_token"])
        except ProfileUpload.DoesNotExist as exc:
            raise ValidationError({"upload_token": "Upload token not found."}) from exc
        if upload.is_expired:
            raise ValidationError({"upload_token": "Upload token has expired; validate the file again."})

        p = upload.parsed_payload
        interval = upload.interval_minutes
        load = ensure_energy(p.get("load_values") or [], upload.value_kind, interval) if p.get("load_values") else None
        pv = ensure_energy(p.get("pv_values") or [], upload.value_kind, interval) if p.get("pv_values") else None
        warnings.extend(upload.warnings or [])

        if load is None:
            raise ValidationError({"upload_token": "This calculation requires a load profile."})

        if pv is None:
            hourly_pv = representative_pv(attrs["pv_size_kw"])
            if interval == 60:
                pv = hourly_pv[: len(load)]
            elif interval > 0 and 60 % interval == 0:
                per_hour = 60 // interval
                pv = []
                for value in hourly_pv:
                    pv.extend([value / per_hour] * per_hour)
                pv = pv[: len(load)]
            else:
                raise ValidationError(
                    {"upload_token": "A load-only file with this interval cannot be aligned to the hourly client algorithm."}
                )
            assumptions.append("The uploaded file supplied load only; PV generation was created from the representative PV profile.")

        if len(pv) != len(load):
            common = min(len(pv), len(load))
            pv = pv[:common]
            load = load[:common]
            warnings.append("PV and load lengths differed; both profiles were truncated to the shared interval count.")

        # Important: a headerless client two-column file contains the legacy base PV
        # profile. We pass it unscaled to the compiled MATLAB function so the original
        # (1742.7/1737) * (PV size / 3) scaling happens inside MATLAB, not in Python.
        legacy_base_profile = "matlab_two_column" in upload.detected_format

        load = _aggregate_hourly(load, interval)
        pv = _aggregate_hourly(pv, interval)
        if interval != 60:
            assumptions.append(
                f"{interval}-minute interval energy was summed into hourly energy before calling the client MATLAB algorithm, "
                "which assumes one-hour steps."
            )
        timestamps = _hourly_timestamps(p.get("timestamps") or [], interval, len(load))
        interval = 60

        if len(pv) != len(load):
            common = min(len(pv), len(load))
            pv = pv[:common]
            load = load[:common]
            timestamps = timestamps[:common]

        if len(load) not in {8760, 8784}:
            warnings.append(
                f"Uploaded profile contains {len(load)} hourly values rather than a complete 8760/8784-hour year. "
                "The client MATLAB algorithm sums the supplied period directly; annual-labelled outputs should only be interpreted as annual when a full-year profile is supplied."
            )

        if legacy_base_profile:
            assumptions.append(
                "Client two-column MATLAB format detected: column 1 is passed as the legacy base PV profile; "
                "the original (1742.7/1737) × (PV size / 3) scaling is applied inside the compiled MATLAB function."
            )

    imp, fit, supply, demand_rate, tariff_name = _flat_tariff_rates(attrs, timestamps, len(load))
    assumptions.append(f"Tariff used: {tariff_name}.")
    assumptions.append(
        "The supplied MATLAB optimisation objective uses battery annual payment + grid import cost - export FIT revenue. "
        "Daily supply charge is retained as metadata but is not inserted into the client's optimisation objective."
    )

    data = EngineInput(
        load_kwh=load,
        pv_kwh=pv,
        interval_hours=1.0,
        import_rates=imp,
        feed_in_rates=fit,
        daily_supply_charge=supply,
        demand_charge_rate_per_kw_day=demand_rate,
        battery_annual_cost_per_kwh=attrs["battery_annual_cost_per_kwh"],
        battery_installed_cost_per_kwh=attrs["battery_installed_cost_per_kwh"],
        max_capacity_kwh=attrs["max_battery_capacity_kwh"],
        pv_size_kw=attrs["pv_size_kw"],
        pv_profile_is_legacy_base=legacy_base_profile,
    )
    return data, assumptions, warnings
