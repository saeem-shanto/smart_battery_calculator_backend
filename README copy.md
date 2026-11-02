# MATLAB / Octave numerical parity kit — Smart Battery Calculator N01

## A. Validate the client source script in both engines

1. Create a fresh `parity-run/` directory.
2. Put a **copy** of the supplied `batt_cal_v1.m` into it (no editing). If your local filename is `batt_cal_v1(1).m`, copying to `batt_cal_v1.m` is a filename change, not an algorithm edit.
3. Add the exact `Vanikavipuldata.xls` referenced by `xlsread` in the script. Do not use random or synthetic annual data for the final reported test unless labelled.
4. Ensure the input has 8,760 rows for the nominal 365-day hourly run and matches the script's first two columns (PV and load), no unexpected headers.
5. In Terminal `cd parity-run`. Run MATLAB: `matlab -batch "run('batt_cal_v1.m')"`, or in the MATLAB Command Window: `run('batt_cal_v1.m')`.
6. Confirm output file `Results_RPAtrail400.csv` was freshly created. Copy to `matlab_result.csv`.
7. Run Octave: `octave --quiet --eval "run('batt_cal_v1.m')"`. If `xlsread` is unavailable, install/configure the Octave `io` package and use `octave --quiet --eval "pkg load io; run('batt_cal_v1.m')"`.
8. Confirm fresh output and copy to `octave_result.csv`.
9. From the kit directory run: `python3 compare_parity.py --matlab /path/to/parity-run/matlab_result.csv --octave /path/to/parity-run/octave_result.csv --report parity_report.md`.
10. Save script SHA-256, workbook SHA-256, engine versions, terminal transcripts, outputs and the report with the assignment evidence.

**IMPORTANT:** Original script hard-codes x=15 kWh, cap_pv=6 kW, daily_avg=14.2766 kWh/day, financing and tariffs. This exercise validates *original script execution parity only*. It is NOT direct validation of a UI scenario at 30 kWh/12 kW with different values.

## B. Validate the deployed parameterised Django / Octave workflow

For **one specific UI scenario**, retain an exact copy of the 8,760-hour generated PV/load values, input configuration (battery capacity, PV size, 24 retail prices, 24 feed-in prices, interest, installation price, loan years and daily supply charge), and the exact backend-generated/parameterised runtime script. Execute that runtime script in both MATLAB and Octave with identical inputs and compare the seven canonical outputs using this tool. Also compare the Django API result numbers to the Octave output (be careful about annual-vs-daily units, rounding, bill without battery and frontend display calculations).

If the backend writes input values by modifying a runtime *copy* of the original MATLAB source, save the generated copy as an evidence artifact, not as the authoritative client source file.

## Known model caveats

- `xlsread('Vanikavipuldata.xls')` may require Octave's `io` package; check compatibility.
- The script explicitly handles the **first hour** differently, including first-hour import cost accumulation. Do not silently fix it in one engine only.
- The client CSV has 7 columns: [battery kWh, annual net payment, export kWh, import kWh, 'Losses' kWh, annual financing instalment, PV kW].
- A matching MATLAB/Octave result confirms reproducibility, not the physical correctness of curtailment or the financial model.
- Use a documented absolute tolerance suited to CSV output precision. This kit defaults to 0.01 in each field's printed units; report an adjusted threshold only with justification.
