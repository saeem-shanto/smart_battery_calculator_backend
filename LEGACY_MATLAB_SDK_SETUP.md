# MATLAB Compiler SDK → Django setup

## Architecture

```text
Next.js
  ↓
Django REST API
  ↓
MatlabCompiledEngine
  ↓
Generated Python package: smartbatterymatlab
  ↓
MATLAB Runtime
  ↓
smart_battery_optimize.m
```

The frontend never calls MATLAB directly.

## 1. Build the Python package

Requirements on the build machine:

- MATLAB
- MATLAB Compiler
- MATLAB Compiler SDK
- a Python release supported by your MATLAB release

In MATLAB:

```matlab
cd('/path/to/smart-battery-backend-matlab-sdk/matlab_sdk_source')
build_python_package
```

The build script runs `compiler.build.pythonPackage` and creates package `smartbatterymatlab`.

## 2. Install the generated package

The build output contains `setup.py`. Activate the same Python environment Django will use, then install from the generated build folder. For example:

```bash
source .venv/bin/activate
pip install ./matlab_sdk_source/build/smartbatterymatlab_python_package
```

Depending on the exact MathWorks-generated folder layout, install the directory containing its `setup.py`.

## 3. Install MATLAB Runtime

Install the MATLAB Runtime release that matches the MATLAB release used for compilation.

### macOS local validation

MathWorks requires using `mwpython` for a Compiler SDK Python package on macOS. Start Django with the `mwpython` executable from MATLAB/Runtime instead of normal `python`, for example:

```bash
/path/to/MATLAB_or_Runtime/bin/mwpython manage.py runserver 0.0.0.0:8000
```

### Linux production/staging

Set:

```env
MATLAB_RUNTIME_OPTIONS=-nojvm,-nodisplay
```

The adapter calls `initialize_runtime()` before `initialize()` and keeps one component handle per Python worker process.

## 4. Configure Django

`.env`:

```env
CALCULATION_ENGINE=matlab_compiled
MATLAB_SDK_PACKAGE=smartbatterymatlab
MATLAB_SDK_FUNCTION=smart_battery_optimize
MATLAB_SERIALIZE_CALLS=True
MATLAB_SDK_TEST_ENABLED=True
```

Run migrations and seed data:

```bash
python manage.py migrate
python manage.py seed_tariffs
python manage.py bootstrap_admin
```

On macOS, replace `python` with `mwpython` for commands that import/initialize the compiled package.

## 5. Verify through Swagger

Open:

```text
http://127.0.0.1:8000/api/docs/
```

First run:

```text
GET /api/v1/matlab-sdk/status/
```

A healthy environment reports:

```json
{
  "runtime_ready": true,
  "package_importable": true,
  "matlab_module_importable": true
}
```

Then test:

```text
POST /api/v1/matlab-sdk/test/
```

or upload the original two-column PV/load workbook to:

```text
POST /api/v1/matlab-sdk/test-file/
```

Finally test the actual website contract:

```text
POST /api/v1/calculations/
```

That endpoint uses the same `MatlabCompiledEngine` and stores the result in the normal Calculation record.

## 6. Important algorithm constraints

The supplied client MATLAB algorithm uses:

- hourly energy steps;
- one scalar retail rate per optimization;
- one scalar feed-in tariff;
- battery SOC limits 0.10 to 0.95;
- battery/charge/discharge efficiencies 0.95/0.96/0.96;
- `fminbnd` bounded battery-size optimization;
- objective: annual battery payment + import cost - export revenue.

Therefore this backend deliberately:

- aggregates supported 5/10/15/30-minute energy profiles into hourly energy before calling MATLAB;
- rejects TOU tariffs instead of averaging them;
- rejects demand charges instead of pretending the original objective supports them;
- applies the legacy PV scaling inside MATLAB for the client's two-column workbook format.

This prevents the website from presenting a result as the client's algorithm when it is actually a modified calculation.

## 7. Production concurrency

MATLAB Runtime is initialized in-process. This backend lazily initializes one compiled component per Python worker and serializes calls inside that worker by default.

For a Runtime-hosting server, start conservatively with one Gunicorn worker:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 1 --timeout 180
```

Increase concurrency only after measuring Runtime memory and validating package behavior.

## 8. Render Free

Do not attempt to run MATLAB Runtime inside the current 512 MB Render Free web service. You can keep the Django/Next.js web layer there only if the compiled algorithm is hosted on a separate suitable machine/service, but this particular backend edition expects the package to be local/in-process when `CALCULATION_ENGINE=matlab_compiled`.

## Client workbook final test

For the supplied two-column workbook, use the direct production-style endpoint:

`POST /api/v1/calculations/client-workbook/`

A copy of the provided fixture is under `samples/Vanikavipuldata_sample.xls`. Run `python manage.py validate_client_workbook samples/Vanikavipuldata_sample.xls` first, then test the endpoint from Swagger or the included Postman collection.
