% Sample used by MATLAB Compiler SDK to generate Python calling examples.
pv = [0 0 0 0 0 0.05 0.15 0.35 0.55 0.75 0.9 1.0 0.95 0.85 0.7 0.5 0.3 0.12 0.03 0 0 0 0 0]';
ld = [0.35 0.3 0.28 0.26 0.3 0.4 0.55 0.6 0.5 0.4 0.35 0.3 0.32 0.35 0.4 0.5 0.75 1.1 1.3 1.0 0.8 0.65 0.5 0.4]';
out = smart_battery_optimize(pv, ld, 5, 50, 0.3773, 0.124, 50, true, 1000);
disp(out);
