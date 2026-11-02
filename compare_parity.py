#!/usr/bin/env python3
"""Compare original client 7-column summary CSV produced by MATLAB and Octave.

Does not implement or reproduce client modelling mathematics.
"""
import argparse
import csv
import math
import hashlib
from pathlib import Path

FIELDS = [
    ("Battery capacity", "kWh"),
    ("Annual net payment", "AUD/year"),
    ("Annual grid export", "kWh"),
    ("Annual grid import", "kWh"),
    ("Energy-balance losses (client output)", "kWh"),
    ("Annual financing instalment", "AUD/year"),
    ("Solar PV capacity", "kW"),
]


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.reader(f) if r and any(x.strip() for x in r)]
    if len(rows) != 1:
        raise ValueError(f"{path}: expected exactly one result row; found {len(rows)}")
    if len(rows[0]) != len(FIELDS):
        raise ValueError(f"{path}: expected 7 columns, found {len(rows[0])}")
    values = [float(x.strip()) for x in rows[0]]
    if not all(math.isfinite(x) for x in values):
        raise ValueError(f"{path}: contains nonfinite output")
    return values


def main():
    p = argparse.ArgumentParser(description="Compare MATLAB and GNU Octave CSV results")
    p.add_argument("--matlab", type=Path, required=True)
    p.add_argument("--octave", type=Path, required=True)
    p.add_argument("--absolute-tolerance", type=float, default=0.01,
                   help="Tolerance for reported numeric summary results (default: 0.01 in each metric's units)")
    p.add_argument("--report", type=Path, default=Path("parity_report.md"))
    a = p.parse_args()
    if a.absolute_tolerance < 0:
        p.error("Tolerance must not be negative")
    x, y = load(a.matlab), load(a.octave)
    entries = []
    lines = ["# MATLAB vs GNU Octave — Numerical Parity", "",
             "Same exact input workbook, same script, same working-directory inputs and model assumptions must be independently confirmed.", "",
             f"Acceptance tolerance: absolute difference ≤ {a.absolute_tolerance:g} for each output (unit indicated per row).", "",
             "| Output | MATLAB | Octave | Absolute difference | Unit | Pass? |",
             "|---|---:|---:|---:|---|---|"]
    for ((name, unit), lhs, rhs) in zip(FIELDS, x, y):
        delta = abs(lhs-rhs)
        ok = delta <= a.absolute_tolerance
        entries.append(ok)
        lines.append(f"| {name} | {lhs:.8f} | {rhs:.8f} | {delta:.8f} | {unit} | {'PASS' if ok else 'FAIL'} |")
    status = "PASS" if all(entries) else "FAIL"
    lines += ["", f"**Overall result: {status} ({sum(entries)}/{len(entries)} fields within tolerance).**", "",
              "## Artifact hashes", ""]
    for key, path in [("MATLAB result", a.matlab), ("Octave result", a.octave)]:
        lines.append(f"- {key}: `{path}` (SHA-256 `{hashlib.sha256(path.read_bytes()).hexdigest()}`)")
    lines += ["", "## Scope and limitations", "",
              "This checks parity of the seven-column client CSV output only. It does not establish correctness of the original equations, individual hourly energy flows, PV generation, backend API transformation, or frontend displays. Run a separate Django end-to-end reconciliation for those.", ""]
    a.report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nReport saved: {a.report}")
    raise SystemExit(0 if all(entries) else 1)

if __name__ == "__main__":
    main()
