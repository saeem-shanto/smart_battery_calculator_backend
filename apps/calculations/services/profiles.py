import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def representative_load(daily_kwh, occupants=2, afternoon=False, days=365):
    # Normalised residential shape; deliberately transparent and replaceable with client-approved profiles.
    base=[0.55,0.48,0.43,0.40,0.42,0.55,0.85,1.15,1.05,0.82,0.72,0.68,0.70,0.75,0.82,0.95,1.20,1.55,1.80,1.75,1.45,1.15,0.90,0.70]
    if afternoon:
        for h in range(12,17): base[h]*=1.18
    total=sum(base)
    hourly=[x/total*daily_kwh for x in base]
    values=[]
    for d in range(days):
        season=1.0+0.10*math.cos(2*math.pi*(d-180)/365)
        day=[x*season for x in hourly]
        scale=daily_kwh/sum(day)
        values.extend([x*scale for x in day])
    return values

def representative_pv(size_kw, days=365):
    values=[]
    for d in range(days):
        seasonal=0.72+0.28*math.sin(2*math.pi*(d-80)/365)
        seasonal=max(0.35,seasonal)
        raw=[]
        for h in range(24):
            if 6<=h<=18:
                raw.append(max(0.0, math.sin(math.pi*(h-6)/12)))
            else: raw.append(0.0)
        # Approx. representative annual yield ~1,600 kWh/kW; not site-specific.
        target_day=size_kw*(1600/365)*seasonal
        s=sum(raw) or 1
        values.extend([x/s*target_day for x in raw])
    return values

def ensure_energy(values, value_kind, interval_minutes):
    if value_kind=="power_kw":
        factor=interval_minutes/60
        return [float(v)*factor for v in values]
    return [float(v) for v in values]

def timestamps_for_length(length, interval_minutes):
    start=datetime(2026,1,1,tzinfo=ZoneInfo("Australia/Adelaide"))
    return [start+timedelta(minutes=i*interval_minutes) for i in range(length)]
