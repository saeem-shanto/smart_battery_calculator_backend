# Smart Battery Calculator Backend — GNU Octave Edition

Django/DRF backend for Project N01. This edition executes the client's MATLAB-compatible battery optimisation with **GNU Octave**, so the deployed Render service does not need MATLAB, MATLAB Runtime, MATLAB Engine, or a MATLAB licence.

## Runtime architecture

```text
Next.js / Vercel
       ↓ REST
Django / Render
       ↓
OctaveEngine
       ↓ subprocess (one calculation at a time)
octave-cli
       ↓
octave_source/smart_battery_optimize.m
       ↓
JSON result
```

The normal calculation endpoints keep the existing database/API contract. The default engine is:

```env
CALCULATION_ENGINE=octave
```

No silent algorithm fallback is used.

## Octave diagnostics

When `OCTAVE_TEST_ENABLED=True`:

```text
GET  /api/v1/octave/status/
POST /api/v1/octave/test/
POST /api/v1/octave/test-file/
```

Swagger:

```text
http://127.0.0.1:8000/api/docs/
```

## Client algorithm source

`octave_source/` contains:

- `smart_battery_optimize.m` — MATLAB-compatible optimisation wrapper
- `run_smart_battery_cli.m` — small file-based bridge used by Django

The original supplied optimisation structure is retained: SOC limits, efficiencies, flat retail/FIT inputs, `fminbnd` battery sizing, and the objective `battery annual payment + import cost - export revenue`.

`matlab_sdk_source/` is retained as a legacy/reference build route but is not needed for the Octave deployment.

## Local start

Install GNU Octave first.

macOS:

```bash
brew install octave
```

Check:

```bash
octave-cli --version
```

Then:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
python manage.py runserver
```

Check the bridge:

```bash
curl http://127.0.0.1:8000/api/v1/octave/status/
```

## Render Free

The Dockerfile installs GNU Octave with `apt-get` and deliberately runs one synchronous Gunicorn worker:

```text
--workers 1 --worker-class sync --threads 1
```

`OctaveEngine` also serializes algorithm calls with a process lock. This reduces the chance of two Octave processes competing for the 512 MB Render Free memory limit.

Free hosting is appropriate for the university prototype and validation deployment, but should not be treated as high-availability production infrastructure.

## Client workbook calculation

```text
POST /api/v1/calculations/client-workbook/
```

Expected workbook convention:

- column 1 = legacy/base PV profile
- column 2 = household load
- each row = one hour

The raw workbook is validated by Django, converted to arrays, then passed to GNU Octave. The uploaded workbook itself is not stored in the `Calculation` payload.

See `OCTAVE_SETUP.md` and `CLIENT_WORKBOOK_GUIDE.md` for deployment and cURL examples.
