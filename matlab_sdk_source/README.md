# MATLAB Compiler SDK source

This folder contains the deployable MATLAB entry point used by Django.

- `smart_battery_optimize.m` — explicit-input wrapper around the client battery optimisation logic.
- `smart_battery_sample.m` — sample call used by the package builder.
- `build_python_package.m` — builds package `smartbatterymatlab` with MATLAB Compiler SDK.

The function intentionally returns a numeric vector because that is a stable and simple boundary between the generated MATLAB package and Django. The first nine values use the semantic result order expected by the project: battery size, net payment, export, import, losses, retail price, battery annual rate, FIT and PV size.

Do not edit the algorithm equations during web integration without client approval. If the client supplies a revised algorithm, update the MATLAB function, rebuild the package, and re-run the API validation cases.
