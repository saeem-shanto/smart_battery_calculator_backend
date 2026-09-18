# Client workbook workflow — GNU Octave backend

This backend supports the client workbook convention from the supplied MATLAB scripts:

- **Column 1:** legacy/base PV profile
- **Column 2:** household load profile
- **Each row:** one hour
- **PV scaling:** `(1742.7 / 1737) * (PV size / 3)` is applied inside `smart_battery_optimize.m`
- **Optimizer:** `fminbnd` over battery capacity
- **Default legacy parameters:** PV size 5 kW, battery annual payment rate 50 AUD/kWh/year, retail price 0.3773 AUD/kWh, FIT 0.124 AUD/kWh, maximum battery 50 kWh

The supplied test workbook is included at:

```text
samples/Vanikavipuldata_sample.xls
```

## Validate the file only

```bash
python manage.py validate_client_workbook samples/Vanikavipuldata_sample.xls
```

## Verify Octave

```text
GET /api/v1/octave/status/
```

## Diagnostic workbook endpoint

```text
POST /api/v1/octave/test-file/
```

This validates the workbook and invokes GNU Octave without creating a normal calculation record.

## Final website endpoint

```text
POST /api/v1/calculations/client-workbook/
```

Multipart fields:

- `file`
- `consent=true`
- `pv_size_kw=5`
- `battery_annual_cost_per_kwh=50`
- `battery_installed_cost_per_kwh=1000`
- `retail_price_per_kwh=0.3773`
- `feed_in_tariff_per_kwh=0.124`
- `max_battery_capacity_kwh=50`

The endpoint validates the workbook, passes PV/load arrays to the Octave engine, creates a standard `Calculation` record and returns the same result/token contract used by the frontend.

## Render deployment

The Docker image includes GNU Octave. The server deliberately uses one Gunicorn sync worker and serialized Octave calls. Keep database persistence external (for example Supabase/PostgreSQL) because the Render filesystem is ephemeral.
