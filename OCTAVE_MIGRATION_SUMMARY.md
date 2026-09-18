# Octave migration summary

This edition was created from `smart-battery-backend-final-client-xls`.

## Added

- `apps/calculations/services/octave_engine.py`
- `apps/octave/` diagnostics API
- `octave_source/smart_battery_optimize.m`
- `octave_source/run_smart_battery_cli.m`
- `OCTAVE_SETUP.md`
- `render.yaml`
- GNU Octave Postman collection

## Changed

- default `CALCULATION_ENGINE` -> `octave`
- client workbook endpoint now uses the configured engine rather than directly constructing the compiled MATLAB engine
- Docker image installs GNU Octave
- Gunicorn restricted to one synchronous worker
- engine factory imports NumPy/SciPy reference engine lazily
- client workbook parser no longer requires pandas
- generic profile parser no longer imports pandas at Django startup
- Swagger metadata and documentation updated for Octave

## Retained

- Calculation database model and response contract
- result access tokens
- workbook validation
- tariffs/profiles/feedback/admin APIs
- existing frontend-facing calculation paths
- legacy compiled-MATLAB engine as an optional non-default backend
