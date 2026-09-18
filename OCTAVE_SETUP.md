# GNU Octave → Django setup

## Why this edition exists

The project needs to execute the client MATLAB algorithm on a small Render deployment without a MATLAB installation or MATLAB Runtime. GNU Octave is used as a MATLAB-compatible execution layer.

## 1. Verify Octave locally

```bash
octave-cli --version
```

On macOS:

```bash
brew install octave
```

## 2. Configure Django

`.env`:

```env
CALCULATION_ENGINE=octave
OCTAVE_EXECUTABLE=octave-cli
OCTAVE_TIMEOUT_SECONDS=120
OCTAVE_SERIALIZE_CALLS=True
OCTAVE_TEST_ENABLED=True
```

## 3. Test Octave status

```bash
python manage.py runserver
curl http://127.0.0.1:8000/api/v1/octave/status/
```

Healthy example:

```json
{
  "runtime_ready": true,
  "octave_executable": "octave-cli",
  "octave_version": "GNU Octave ..."
}
```

## 4. Test arrays directly

```bash
curl -X POST http://127.0.0.1:8000/api/v1/octave/test/ \
  -H 'Content-Type: application/json' \
  -d '{
    "pv_profile": [0,0,0.5,1.2,2.5,3,2,1,0.2,0],
    "load_profile": [0.8,0.7,0.6,0.8,1,1.2,1.3,1.4,1,0.9],
    "profile_is_base_pv": true,
    "pv_size_kw": 5,
    "battery_annual_cost_per_kwh": 50,
    "battery_installed_cost_per_kwh": 1000,
    "retail_price_per_kwh": 0.3773,
    "feed_in_tariff_per_kwh": 0.124,
    "max_battery_capacity_kwh": 50
  }'
```

## 5. Test the supplied client workbook

```bash
curl -X POST http://127.0.0.1:8000/api/v1/octave/test-file/ \
  -F 'file=@samples/Vanikavipuldata_sample.xls' \
  -F 'pv_size_kw=5' \
  -F 'battery_annual_cost_per_kwh=50' \
  -F 'battery_installed_cost_per_kwh=1000' \
  -F 'retail_price_per_kwh=0.3773' \
  -F 'feed_in_tariff_per_kwh=0.124' \
  -F 'max_battery_capacity_kwh=50'
```

## 6. Test the real calculation endpoint

```bash
curl -X POST http://127.0.0.1:8000/api/v1/calculations/client-workbook/ \
  -F 'file=@samples/Vanikavipuldata_sample.xls' \
  -F 'consent=true' \
  -F 'pv_size_kw=5' \
  -F 'battery_annual_cost_per_kwh=50' \
  -F 'battery_installed_cost_per_kwh=1000' \
  -F 'retail_price_per_kwh=0.3773' \
  -F 'feed_in_tariff_per_kwh=0.124' \
  -F 'max_battery_capacity_kwh=50'
```

## 7. Render

The included Dockerfile installs `octave` and starts a single synchronous Gunicorn worker. Recommended environment variables:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
CALCULATION_ENGINE=octave
OCTAVE_EXECUTABLE=octave-cli
OCTAVE_TIMEOUT_SECONDS=120
OCTAVE_SERIALIZE_CALLS=True
OCTAVE_TEST_ENABLED=True
```

Set `SECRET_KEY`, `DATABASE_URL`, CORS origins and other production values separately.

## 8. Scientific validation

Octave is MATLAB-compatible but not MATLAB itself. Before treating the deployed outputs as validated research outputs, compare multiple identical input cases against MATLAB and record tolerances for battery size, net payment, import/export, losses and derived values.
