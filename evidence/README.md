# N01 Smart Battery Calculator — Verification Evidence (GitHub Folder)

**Group M262H-9104** · Compiled 2 November 2026

This folder collects **selected, genuine verification artifacts** from the existing
backend GitHub repository, with their original Git blob identities verified. It is
suitable as a starting `evidence/` directory for a developer handover.

## Contents

- `tests_snapshot/` — archived copies of the backend's adapter and generated-profile
  tests, plus a CSV comparison script. These are source snapshots, not new test runs.
- `reference_results/` — an existing seven-field Octave output CSV and result CSV.
- `logs/` — an existing Octave output log for that sample execution.
- `source_integrity/` — SHA-256 records for three client-owned MATLAB model files.
- `documentation/EVIDENCE_STATUS.md` — what is and is not supported by this ZIP.
- `PROVENANCE.json` — exact source paths on GitHub; retained Git blob identity.
- `SHA256SUMS.txt` — integrity hashes for the files within this folder.

## Important limitations

**This is NOT the complete original 27 October Verification Evidence ZIP.**
The original submitted archive was not available in this conversation.
The independent Python oracle, 54-test run logs, patched 20-test execution log,
clean-reproduction log, full `run_all.sh`, azimuth patch files and complete
frontend verification artifacts have **not** been reproduced or invented.

The final report records 54/54 baseline checks and 20/20 patched data-pipeline
checks, but those figures have not been independently rerun in preparing this folder.
The report also records the full Django suite as 58/59 passed, with one unresolved test.

## Using the test scripts

The files in `tests_snapshot/` are *reference copies*. Their original relative paths
must be preserved for normal test execution. Run tests in the backend repository,
not inside this standalone evidence directory:

```bash
cd smart_battery_calculator_backend
python -m unittest discover -s tests -v
python manage.py test apps.calculations.tests_generated
```

These commands are guidance, **not evidence of a successful run**. They require
the project's dependencies and configuration. Capture dated results and include
reproducible commands in your complete evidence handover.

For parity comparison, supply independently obtained MATLAB and Octave CSVs:
```bash
python matlab_source_v1/compare_parity.py --matlab MATLAB_results.csv --octave octave_results.csv
```
The packaged `octave_result.csv` is NOT a MATLAB reference output.

## GitHub upload

Copy the `evidence/` folder into the backend repository and review all files
before committing. Do not publish test reports containing user data, environment
variables, access tokens, or other sensitive information. Existing credential
exposure in the project's public Git history must be remediated separately:
deleting a file from a new commit does not remove its historical copies.

Client-owned MATLAB source files are deliberately not duplicated in this folder.
Check ownership/licensing permission before publishing them.

Source repository: https://github.com/saeem-shanto/smart_battery_calculator_backend
