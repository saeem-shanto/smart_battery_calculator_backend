# Client MATLAB algorithm → GNU Octave deployment mapping

The production calculation path is split into two responsibilities.

## Django responsibility

- validate public inputs and uploaded files;
- convert/aggregate supported interval profiles to hourly energy when required;
- reject TOU/demand-charge inputs that the supplied objective does not implement;
- serialize calls to the numerical engine;
- write temporary PV/load vectors;
- invoke `octave-cli` with a fixed project-owned wrapper;
- parse the machine-readable result vector;
- store and return the result through the stable REST contract.

## MATLAB-compatible algorithm responsibility

`octave_source/smart_battery_optimize.m` contains the calculation logic:

- legacy PV base-profile scaling `(1742.7/1737) × (PV size / 3)`;
- battery capacity optimisation with `fminbnd`;
- SOC minimum/maximum 0.10/0.95;
- battery, charge and discharge efficiencies 0.95/0.96/0.96;
- hourly grid import/export and SOC transitions;
- annual battery payment `x × Ab`;
- import cost `Import × retail price`;
- export revenue `Export × FIT`;
- net-payment objective `battery payment + import cost - export revenue`.

`octave_source/run_smart_battery_cli.m` is only a transport wrapper. It reads the two temporary vectors, calls `smart_battery_optimize`, and prints a tagged result line for Django.

## No hidden fallback

When `CALCULATION_ENGINE=octave`, missing GNU Octave or an algorithm failure returns an explicit 503/502 response. The backend never replaces a failed Octave calculation with the reference Python implementation.

## Validation boundary

GNU Octave is MATLAB-compatible but not MATLAB. Scientific acceptance therefore requires MATLAB-vs-Octave reference tests on multiple client-approved scenarios within documented numeric tolerances.
