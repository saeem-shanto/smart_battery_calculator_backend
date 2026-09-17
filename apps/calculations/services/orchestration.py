from datetime import datetime
from dateutil import parser as dtparser
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.profiles.models import ProfileUpload
from apps.tariffs.models import TariffPlan
from .interfaces import EngineInput
from .profiles import representative_load, representative_pv, ensure_energy, timestamps_for_length

def _tariff_rates(attrs,timestamps,n):
    if attrs.get("tariff_id"):
        try: plan=TariffPlan.objects.get(id=attrs["tariff_id"],is_active=True)
        except TariffPlan.DoesNotExist as exc: raise ValidationError({"tariff_id":"Tariff not found or inactive."}) from exc
        feed=[float(plan.feed_in_rate)]*n
        if plan.kind==TariffPlan.Kind.FLAT:
            if plan.flat_import_rate is None: raise ValidationError({"tariff_id":"Flat tariff is missing its import rate."})
            imp=[float(plan.flat_import_rate)]*n
        else:
            peak=float(plan.peak_import_rate or 0); shoulder=float(plan.shoulder_import_rate or peak); off=float(plan.offpeak_import_rate or shoulder)
            imp=[]
            for ts in timestamps:
                h=ts.hour
                if plan.peak_start_hour<=h<plan.peak_end_hour: imp.append(peak)
                elif plan.shoulder_start_hour<=h<plan.shoulder_end_hour: imp.append(shoulder)
                else: imp.append(off)
        return imp,feed,float(plan.daily_supply_charge),float(plan.demand_charge_rate_per_kw_day),f"{plan.provider} {plan.name}".strip()
    return [float(attrs["custom_import_rate"])]*n,[float(attrs.get("custom_feed_in_rate") or 0)]*n,float(attrs.get("custom_daily_supply_charge") or 0),float(attrs.get("custom_demand_charge_rate_per_kw_day") or 0),"Custom tariff"

def build_engine_input(attrs):
    assumptions=[]; warnings=[]
    mode=attrs["source_mode"]
    if mode=="simplified":
        interval=60
        load=representative_load(attrs["daily_consumption_kwh"],attrs.get("occupants",2),attrs.get("afternoon_occupancy",False))
        pv=representative_pv(attrs["pv_size_kw"])
        timestamps=timestamps_for_length(len(load),interval)
        assumptions += [
            "Household demand uses a transparent representative hourly profile scaled to the entered daily consumption.",
            "PV generation uses a representative annual solar shape and is not a postcode-specific weather simulation.",
        ]
    else:
        try: upload=ProfileUpload.objects.get(id=attrs["upload_token"])
        except ProfileUpload.DoesNotExist as exc: raise ValidationError({"upload_token":"Upload token not found."}) from exc
        if upload.is_expired: raise ValidationError({"upload_token":"Upload token has expired; validate the file again."})
        p=upload.parsed_payload; interval=upload.interval_minutes
        load=ensure_energy(p.get("load_values") or [],upload.value_kind,interval) if p.get("load_values") else None
        pv=ensure_energy(p.get("pv_values") or [],upload.value_kind,interval) if p.get("pv_values") else None
        warnings.extend(upload.warnings or [])
        if pv is not None and "matlab_two_column" in upload.detected_format:
            scale = (1742.7 / 1737.0) * (attrs["pv_size_kw"] / 3.0)
            pv = [v * scale for v in pv]
            assumptions.append("Client two-column MATLAB format detected: PV column scaled by (1742.7/1737) × (entered PV size / 3), matching natpaymenttrail.m.")
        if load is None: raise ValidationError({"upload_token":"This calculation requires a load profile. Upload load or combined PV/load data."})
        if pv is None:
            # Generate PV at same resolution by creating hourly PV and spreading each hour across subintervals.
            hourly=representative_pv(attrs["pv_size_kw"])
            per_hour=max(1,round(60/interval))
            pv=[]
            for val in hourly:
                pv.extend([val/per_hour]*per_hour)
            pv=pv[:len(load)]
            assumptions.append("The uploaded file supplied load only; PV generation was created from the representative PV profile.")
        if len(pv)!=len(load):
            m=min(len(pv),len(load)); pv=pv[:m]; load=load[:m]
            warnings.append("PV and load lengths differed; both profiles were truncated to the shared interval count.")
        raw_ts=p.get("timestamps") or []
        if len(raw_ts)>=len(load):
            timestamps=[]
            for x in raw_ts[:len(load)]:
                try: timestamps.append(dtparser.parse(x))
                except Exception: timestamps=[]; break
        else: timestamps=[]
        if not timestamps: timestamps=timestamps_for_length(len(load),interval)
    imp,fit,supply,demand_rate,tariff_name=_tariff_rates(attrs,timestamps,len(load))
    assumptions.append(f"Tariff used: {tariff_name}.")
    data=EngineInput(load_kwh=load,pv_kwh=pv,interval_hours=interval/60,import_rates=imp,feed_in_rates=fit,
                     daily_supply_charge=supply,demand_charge_rate_per_kw_day=demand_rate,
                     battery_annual_cost_per_kwh=attrs["battery_annual_cost_per_kwh"],
                     battery_installed_cost_per_kwh=attrs["battery_installed_cost_per_kwh"],max_capacity_kwh=attrs["max_battery_capacity_kwh"],
                     pv_size_kw=attrs["pv_size_kw"])
    return data,assumptions,warnings
