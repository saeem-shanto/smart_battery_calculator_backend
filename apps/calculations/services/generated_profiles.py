"""Generate a legacy-compatible PV/load CSV without changing client MATLAB sources."""
from __future__ import annotations
import base64
import csv
import io
import math
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from django.core.cache import cache


class ProfileGenerationError(ValueError):
    pass


STATE_ZONES = {"SA": "Australia/Adelaide", "NSW": "Australia/Sydney", "VIC": "Australia/Melbourne", "ACT": "Australia/Sydney", "QLD": "Australia/Brisbane", "WA": "Australia/Perth", "TAS": "Australia/Hobart", "NT": "Australia/Darwin"}
LEGACY_PV_MULTIPLIER = (1742.7 / 1737.0) * (5.0 / 3.0)


def postcode_coordinates(postcode: str, state: str):
    """Look up an Australian postcode using Zippopotam.us. Require state disambiguation."""
    key = f"postcode-v1:{postcode}:{state}"
    cached = cache.get(key)
    if cached:
        return cached
    try:
        response = requests.get(f"https://api.zippopotam.us/au/{postcode}", timeout=12)
        response.raise_for_status()
        places = response.json().get("places", [])
    except requests.RequestException as exc:
        raise ProfileGenerationError("Postcode lookup unavailable. Try again later.") from exc
    matches = [p for p in places if str(p.get("state abbreviation", "")).upper() == state]
    if not matches:
        raise ProfileGenerationError("Postcode was not found in the selected state. Check the postcode and state.")
    # Multiple suburbs may share a postcode. Use the first location as an approximate postcode centroid.
    p = matches[0]
    result = {"latitude": float(p["latitude"]), "longitude": float(p["longitude"]), "place": p.get("place name", ""), "approximate": len(matches) > 1}
    cache.set(key, result, 86400 * 30)
    return result


def _parse_utc_timestamp(stamp: object) -> datetime:
    """Accept API UTC timestamps in ISO 8601 or Unix seconds/milliseconds."""
    raw = str(stamp).strip()
    try:
        if raw.isdecimal() or (raw.startswith("-") and raw[1:].isdecimal()):
            digits = len(raw.lstrip("-"))
            if digits == 13:
                seconds = int(raw) / 1000
            elif digits == 10:
                seconds = int(raw)
            else:
                raise ValueError("Unexpected numeric timestamp length")
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise ProfileGenerationError(
            f"Renewables.ninja returned an invalid UTC timestamp: {raw[:40]!r}."
        ) from exc


def ninja_azimuth(compass_deg: float, lat: float) -> float:
    """Map user compass bearing to Renewables.ninja/GSEE's azimuth convention.

    Users specify 0=N, 90=E, 180=S, 270=W. GSEE uses 180 for
    equator-facing PV, so southern-hemisphere bearings rotate by 180.
    """
    bearing = float(compass_deg) % 360.0
    return bearing if lat >= 0 else (bearing + 180.0) % 360.0


def _annual_pv(lat: float, lon: float, zone: str, year: int, tilt: float, azimuth: float, loss: float):
    ninja_azim = ninja_azimuth(azimuth, lat)
    # The new namespace prevents reuse of profiles cached with the old azimuth.
    key = f"ninja-pv-v4:{lat}:{lon}:{year}:{tilt}:{ninja_azim}:{loss}"
    saved = cache.get(key)
    if saved is not None:
        return saved
    token = os.environ.get("RENEWABLES_NINJA_API_TOKEN", "").strip()
    if not token:
        raise ProfileGenerationError("RENEWABLES_NINJA_API_TOKEN is not configured on the Django server.")
    params = {"lat": lat, "lon": lon, "date_from": f"{year}-01-01", "date_to": f"{year}-12-31", "dataset": "merra2", "capacity": 5, "system_loss": loss, "tracking": 0, "tilt": tilt, "azim": ninja_azim, "format": "json", "local_time": "false"}
    try:
        response = requests.get("https://www.renewables.ninja/api/data/pv", params=params, headers={"Authorization": f"Token {token}"}, timeout=90)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProfileGenerationError("Could not fetch hourly solar data from Renewables.ninja. Check the API configuration and quota.") from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not data:
        raise ProfileGenerationError("Renewables.ninja returned no hourly generation data.")
    tz = ZoneInfo(zone)
    buckets: dict[tuple[int, int, int], list[float]] = {}
    for stamp, item in data.items():
        # An API response may contain an invalid row. Identify the offending
        # timestamp and field rather than hiding the underlying data issue.
        dt = _parse_utc_timestamp(stamp)
        if isinstance(item, dict):
            # Renewables.ninja documents 'electricity' (kW). 'output' is a
            # backward-compatible fallback, only when 'electricity' is absent.
            field = "electricity" if "electricity" in item else "output"
            if field not in item:
                raise ProfileGenerationError(
                    f"Renewables.ninja PV record at {stamp} has no electricity/output field "
                    f"(available fields: {', '.join(sorted(map(str, item.keys())))[:140]})."
                )
            raw_value = item[field]
        else:
            raw_value = item
        if raw_value is None or isinstance(raw_value, bool):
            raise ProfileGenerationError(
                f"Renewables.ninja PV record at {stamp} contains a missing or invalid generation value."
            )
        try:
            value = float(raw_value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ProfileGenerationError(
                f"Renewables.ninja PV record at {stamp} is not a numeric generation value "
                f"(value type: {type(raw_value).__name__})."
            ) from exc
        if not math.isfinite(value) or value < 0:
            raise ProfileGenerationError(
                f"Renewables.ninja PV record at {stamp} contains a non-finite or negative generation value."
            )
        local = dt.astimezone(tz)
        buckets.setdefault((local.month, local.day, local.hour), []).append(value)
    result = []
    day = datetime(year, 1, 1)
    while day.year == year:
        if day.month == 2 and day.day == 29:
            day += timedelta(days=1)
            continue
        for hour in range(24):
            key_hour = (day.month, day.day, hour)
            values = buckets.get(key_hour)
            if not values:
                # DST spring-forward has a missing local hour: approximate from adjacent hours.
                prev_hour = buckets.get(((day + timedelta(hours=hour-1)).month, (day + timedelta(hours=hour-1)).day, (day + timedelta(hours=hour-1)).hour), [])
                next_hour = buckets.get(((day + timedelta(hours=hour+1)).month, (day + timedelta(hours=hour+1)).day, (day + timedelta(hours=hour+1)).hour), [])
                if prev_hour and next_hour:
                    values = [(sum(prev_hour)/len(prev_hour) + sum(next_hour)/len(next_hour))/2]
                elif day.month == 1 and day.day == 1:
                    # UTC-year API window misses the first local hours. Wrap from the same clock-hour on Dec 31.
                    values = buckets.get((12, 31, hour))
            if not values:
                raise ProfileGenerationError(f"Solar profile is missing local hour {day:%Y-%m-%d} {hour:02d}:00; cannot build a complete year.")
            result.append(sum(values) / len(values))
        day += timedelta(days=1)
    if len(result) != 8760:
        raise ProfileGenerationError("Solar profile must contain exactly 8,760 hourly values.")
    cache.set(key, result, 86400)
    return result


def build_generated_profile(*, postcode: str, state: str, load: list[float], year: int, tilt: float, azimuth: float, loss: float):
    if len(load) != 24 or any(not math.isfinite(v) or v < 0 for v in load):
        raise ProfileGenerationError("Provide 24 finite, non-negative hourly load values in kWh.")
    location = postcode_coordinates(postcode, state)
    pv_actual = _annual_pv(location["latitude"], location["longitude"], STATE_ZONES[state], year, tilt, azimuth, loss)
    # The immutable MATLAB source multiplies its first input column by this legacy multiplier.
    # Inverse-scale physical 5-kW PV generation so MATLAB uses the intended actual PV profile once.
    pv_base = [pv / LEGACY_PV_MULTIPLIER for pv in pv_actual]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["PV Generation", "Load Data"])
    for hour in range(8760):
        writer.writerow([f"{pv_base[hour]:.9f}", f"{load[hour % 24]:.9f}"])
    raw = output.getvalue().encode("utf-8")
    return {"filename": f"annual_pv_load_{postcode}_{year}.csv", "csv_bytes": raw, "row_count": 8760, "annual_pv_kwh": round(sum(pv_actual), 3), "annual_load_kwh": round(sum(load) * 365, 3), "location": location, "year": year, "warnings": ["The 24-hour household load is repeated for 365 days; seasonal behaviour is not modelled. Leap-day PV data is omitted when using a leap year.", "The client's original fixed 5 kW PV system and MATLAB optimisation constants are preserved.", "PV timestamps are converted from UTC to local standard/wall-clock hour; DST duplicate hours are averaged, missing hours interpolated, and the initial UTC boundary uses the previous December clock-hour as an approximation."]}



def build_generated_csv(**kwargs):
    """Backward-compatible preview endpoint payload, not used in the direct workflow."""
    profile = build_generated_profile(**kwargs)
    raw = profile.pop("csv_bytes")
    profile["csv_base64"] = base64.b64encode(raw).decode("ascii")
    return profile
