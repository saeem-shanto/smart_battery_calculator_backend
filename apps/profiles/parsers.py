import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from dateutil import parser as dtparser

MAX_POINTS = 110_000

class ProfileParseError(ValueError):
    pass

@dataclass
class ParsedProfile:
    detected_format: str
    interval_minutes: int
    value_kind: str
    load_values: list[float] | None
    pv_values: list[float] | None
    timestamps: list[str] | None
    warnings: list[str]

def _num(v):
    try:
        x=float(str(v).strip())
        if not math.isfinite(x): raise ValueError
        return x
    except Exception as exc:
        raise ProfileParseError(f"Non-numeric interval value: {v!r}") from exc

def _validate_values(values, label):
    if not values:
        raise ProfileParseError(f"No {label} interval values were found.")
    if len(values) > MAX_POINTS:
        raise ProfileParseError(f"Too many intervals ({len(values)}). Maximum supported is {MAX_POINTS}.")
    if any(v < 0 for v in values):
        raise ProfileParseError(f"{label} values cannot be negative.")

def _infer_interval(timestamps, supplied):
    if supplied:
        return int(supplied)
    if timestamps and len(timestamps) >= 2:
        try:
            a=dtparser.parse(timestamps[0]); b=dtparser.parse(timestamps[1])
            mins=round((b-a).total_seconds()/60)
            if mins in {5,10,15,30,60}: return mins
        except Exception:
            pass
    return 60

def _parse_nem12(rows, role):
    if role != "load":
        raise ProfileParseError("NEM12 uploads are treated as household load data in this API.")
    interval = 5
    values = []
    timestamps = []
    warnings = []
    current_interval = interval
    channel_count = 0
    channel_has_data = False

    for row in rows:
        if not row:
            continue
        rec = row[0].strip()
        if rec == "200":
            if channel_has_data:
                raise ProfileParseError(
                    "Multiple NEM12 interval channels were detected. The backend will not silently merge channels. "
                    "Export or select the household consumption channel as a separate file before calculation."
                )
            channel_count += 1
            try:
                current_interval = int(float(row[8]))
            except Exception:
                pass
        elif rec == "300":
            if len(row) < 3:
                continue
            channel_has_data = True
            date_text = row[1].strip()
            n = int(24 * 60 / current_interval)
            dayvals = []
            for cell in row[2 : 2 + n]:
                if str(cell).strip() == "":
                    break
                dayvals.append(_num(cell))
            if not dayvals:
                continue
            values.extend(dayvals)
            try:
                d = dtparser.parse(date_text)
                for i in range(len(dayvals)):
                    timestamps.append(
                        (d + timedelta(minutes=i * current_interval)).isoformat()
                    )
            except Exception:
                timestamps = []
            interval = current_interval

    _validate_values(values, "load")
    if len(values) < 24 * 60 / interval:
        warnings.append("The NEM12 file contains less than one day of interval data.")
    return ParsedProfile(
        "nem12_single_channel",
        interval,
        "energy_kwh_interval",
        values,
        None,
        timestamps or None,
        warnings,
    )

def _is_header(row):
    s=[str(x).strip().lower() for x in row]
    words={"timestamp","datetime","date","time","value","kwh","load","load_kwh","consumption","consumption_kwh","usage","energy","pv","pv_kwh","generation","generation_kwh","solar"}
    return any(x in words or re.fullmatch(r"value\d+", x or "") for x in s)

def _parse_table(rows, role, value_kind, interval_minutes):
    warnings=[]
    header=[str(x).strip().lower() for x in rows[0]] if _is_header(rows[0]) else None
    data=rows[1:] if header else rows
    if header and any(re.fullmatch(r"value\d+", h or "") for h in header):
        value_idxs=[i for i,h in enumerate(header) if re.fullmatch(r"value\d+",h or "")]
        date_idx=next((i for i,h in enumerate(header) if h in {"date","timestamp","datetime"}),None)
        vals=[]; stamps=[]
        for row in data:
            if not row: continue
            dayvals=[_num(row[i]) for i in value_idxs if i<len(row) and str(row[i]).strip()!=""]
            vals.extend(dayvals)
            if date_idx is not None and date_idx<len(row):
                try:
                    d=dtparser.parse(str(row[date_idx]))
                    inferred=interval_minutes or int(24*60/max(1,len(dayvals)))
                    stamps.extend([(d+timedelta(minutes=j*inferred)).isoformat() for j in range(len(dayvals))])
                except Exception: pass
        interval=interval_minutes or int(24*60/max(1,len(value_idxs)))
        _validate_values(vals, role)
        return ParsedProfile("wide_daily_intervals", interval, value_kind if value_kind!="auto" else "energy_kwh_interval", vals if role=="load" else None, vals if role=="pv" else None, stamps or None, warnings)

    def idx(names):
        if not header: return None
        return next((i for i,h in enumerate(header) if h in names),None)
    ts_idx=idx({"timestamp","datetime","date_time","time","date"})
    load_idx=idx({"load","consumption","usage","load_kwh","consumption_kwh"})
    pv_idx=idx({"pv","generation","solar","pv_kwh","generation_kwh"})
    value_idx=idx({"value","kwh","energy"})
    load=[]; pv=[]; stamps=[]
    if role=="combined":
        if header and load_idx is not None and pv_idx is not None:
            for row in data:
                if len(row)<=max(load_idx,pv_idx): continue
                load.append(_num(row[load_idx])); pv.append(_num(row[pv_idx]))
                if ts_idx is not None and ts_idx<len(row): stamps.append(str(row[ts_idx]))
        elif not header and all(len(r)>=2 for r in data if r):
            for row in data:
                if not row: continue
                pv.append(_num(row[0])); load.append(_num(row[1]))
            warnings.append("No header was found; combined data was interpreted as column 1 = PV and column 2 = load, matching the supplied MATLAB workbook convention.")
            detected = "matlab_two_column"
        else:
            raise ProfileParseError("Combined upload needs PV and load columns (or two headerless numeric columns).")
    else:
        chosen = load_idx if role=="load" and load_idx is not None else pv_idx if role=="pv" and pv_idx is not None else value_idx
        if chosen is None:
            if not header and all(len(r)>=1 for r in data if r): chosen=0
            else: raise ProfileParseError(f"Could not identify a numeric {role} value column.")
        target=load if role=="load" else pv
        for row in data:
            if not row or chosen>=len(row) or str(row[chosen]).strip()=="": continue
            target.append(_num(row[chosen]))
            if ts_idx is not None and ts_idx<len(row): stamps.append(str(row[ts_idx]))
    if load: _validate_values(load,"load")
    if pv: _validate_values(pv,"PV")
    interval=_infer_interval(stamps, interval_minutes)
    kind=value_kind if value_kind!="auto" else "energy_kwh_interval"
    if value_kind=="auto": warnings.append("Values were assumed to be interval energy (kWh). Choose value_kind='power_kw' if the file contains average kW instead.")
    detected = locals().get("detected", "timestamp_or_column_csv")
    return ParsedProfile(detected, interval, kind, load or None, pv or None, stamps or None, warnings)

def parse_profile_file(uploaded_file, role, value_kind="auto", interval_minutes=None):
    suffix=Path(uploaded_file.name).suffix.lower()
    raw=uploaded_file.read()
    if suffix in {".xls",".xlsx"}:
        # Spreadsheet parsing is relatively heavy; import pandas only when this
        # generic upload path actually receives an Excel file.
        import pandas as pd
        engine="xlrd" if suffix==".xls" else "openpyxl"
        df=pd.read_excel(io.BytesIO(raw), engine=engine, header=None)
        rows=[["" if pd.isna(v) else v for v in row] for row in df.values.tolist()]
        # If the first row looks like headers, preserve it as strings and use the table parser.
        result=_parse_table(rows, role, value_kind, interval_minutes)
        result.detected_format="excel_"+result.detected_format
        return result
    if suffix not in {".csv",".txt"}:
        raise ProfileParseError("Supported upload types are CSV, TXT, XLS, and XLSX.")
    try: text=raw.decode("utf-8-sig")
    except UnicodeDecodeError: text=raw.decode("latin-1")
    rows=[row for row in csv.reader(io.StringIO(text)) if row and any(str(c).strip() for c in row)]
    if not rows: raise ProfileParseError("The uploaded file is empty.")
    first=str(rows[0][0]).strip().upper()
    if first in {"NEM12","100"} or any(str(r[0]).strip()=="300" for r in rows[:50] if r):
        return _parse_nem12(rows,role)
    return _parse_table(rows,role,value_kind,interval_minutes)
