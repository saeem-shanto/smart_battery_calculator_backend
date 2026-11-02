# Verification evidence status

Source: N01 Smart Battery Calculator Final Project Report, Section 5 and handover Table 18,
plus actual selected files fetched from the backend GitHub `main` branch on 2 November 2026.

| Evidence item | Status in this folder |
|---|---|
| Backend profile/time tests | **Included** as unchanged code snapshots, not executed here |
| Version 2 adapter test | **Included** as unchanged code snapshot, not executed here |
| CSV parity comparison utility | **Included** as unchanged source; requires independent MATLAB result |
| Existing seven-field Octave result and console log | **Included** |
| Client source SHA-256 record (3 source files) | **Included** as existing repository document |
| Independent numerical oracle source | **Not available** |
| Complete 54/54 baseline execution log and `run_all.sh` | **Not available** |
| 20/20 patched pipeline log and azimuth v1.8.4 patch | **Not available** |
| Full Django 59-test execution log (report states 58 passed, 1 failed) | **Not available** |
| SHA-256 manifest of this ZIP's collected files | **Included** (generated at packaging) |
| Client acceptance/sign-off | **Not provided** |

## Reporting language

Use **“Verification evidence (selected GitHub snapshots)”** for this ZIP.
Do **not** label it the full 27 October handover evidence archive or claim that
all 54, 20, or 59 tests were rerun here.

## Outstanding handover actions

1. Rotate exposed credentials, remedy public repository history, retest security.
2. Merge/deploy PV azimuth correction; clear old PV cache; retest both model versions.
3. Fix remaining Django execution-log test; rerun and attach dated full-suite output.
4. Complete accessibility and client/mentor acceptance checks.
