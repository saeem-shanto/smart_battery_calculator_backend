function out = smart_battery_optimize(pv_input, ld_input, cap_pv, Ab, rp, fit, max_battery_kwh, profile_is_base_pv, installed_cost_per_kwh)
%SMART_BATTERY_OPTIMIZE Deployable wrapper for the client's battery algorithm.
%
% First nine outputs intentionally match the intended Results_RPAtrail400
% semantic layout:
% [battery_size, net_payment, export, import, losses, retail_price,
%  battery_annual_rate, FIT, PV_size]
%
% Remaining outputs support the web dashboard while the optimization itself
% remains the supplied objective: x*Ab + Import*rp - Export*fit.

pv_input = double(pv_input(:));
ld = double(ld_input(:));

if isempty(pv_input) || isempty(ld)
    error('smartbattery:EmptyProfile', 'PV and load profiles cannot be empty.');
end
if numel(pv_input) ~= numel(ld)
    error('smartbattery:ProfileLength', 'PV and load profiles must have the same length.');
end
if any(~isfinite(pv_input)) || any(~isfinite(ld)) || any(pv_input < 0) || any(ld < 0)
    error('smartbattery:ProfileValues', 'PV/load profiles must contain finite non-negative values.');
end

cap_pv = double(cap_pv);
Ab = double(Ab);
rp = double(rp);
fit = double(fit);
max_battery_kwh = double(max_battery_kwh);
profile_is_base_pv = logical(profile_is_base_pv);
installed_cost_per_kwh = double(installed_cost_per_kwh);

% Preserve natpaymenttrail.m PV scaling only for the client's base-profile
% workbook convention. Generic uploaded PV profiles are already site energy.
if profile_is_base_pv
    pv2 = pv_input .* (1742.7 / 1737.0);
    pv = cap_pv .* pv2 ./ 3.0;
else
    pv = pv_input;
end

lb = 0;
ub = max_battery_kwh;
objective = @(x) battery_objective(x, pv, ld, Ab, rp, fit);
[x, fval, exitflag] = fminbnd(objective, lb, ub);

[~, Exp, Imp, Losses] = battery_objective(x, pv, ld, Ab, rp, fit);

% No-battery baseline for web comparison. This is derived from the same PV and
% load energy balance, without modifying the optimized client objective.
pd0 = pv - ld;
base_export = sum(max(pd0, 0));
base_import = sum(max(-pd0, 0));
baseline_net = base_import * rp - base_export * fit;

bill_reduction = baseline_net - fval;
if abs(baseline_net) > eps
    bill_reduction_pct = (bill_reduction / baseline_net) * 100;
else
    bill_reduction_pct = 0;
end

upfront_cost = x * installed_cost_per_kwh;
if bill_reduction > eps
    payback = upfront_cost / bill_reduction;
else
    payback = -1; % sentinel parsed as null by Django
end

annual_pv = sum(pv);
annual_load = sum(ld);
if annual_pv > eps
    self_consumption = max(0, annual_pv - Exp) / annual_pv * 100;
    baseline_self = max(0, annual_pv - base_export) / annual_pv * 100;
else
    self_consumption = 0;
    baseline_self = 0;
end

out = [ ...
    x, ...                         % 1 optimal battery size
    fval, ...                      % 2 net annual payment
    Exp, ...                       % 3 export
    Imp, ...                       % 4 import
    Losses, ...                    % 5 legacy losses = import - export
    rp, ...                        % 6 retail price
    Ab, ...                        % 7 battery annual payment rate
    fit, ...                       % 8 FIT
    cap_pv, ...                    % 9 PV size
    fval, ...                      % 10 objective value
    exitflag, ...                  % 11 optimizer exit flag
    baseline_net, ...              % 12 baseline payment
    bill_reduction, ...            % 13 reduction
    bill_reduction_pct, ...        % 14 reduction percent
    upfront_cost, ...              % 15 battery upfront cost
    payback, ...                   % 16 simple payback
    self_consumption, ...          % 17 optimized self-consumption
    baseline_self, ...             % 18 baseline self-consumption
    annual_load, ...               % 19 load energy
    annual_pv ...                  % 20 PV energy
];
end


function [f, Exp, Imp, Losses] = battery_objective(x, pv, ld, Ab, rp, fit)
%BATTERY_OBJECTIVE Refactor of supplied battrail.m with the same SOC/cost logic.

socmin = 0.10;
socmax = 0.95;
effb = 0.95;
effc = 0.96;
effd = 0.96;
nn = length(pv);

Pd = zeros(nn,1);
soc = zeros(nn,1);
exp_grid = zeros(nn,1);
imp = zeros(nn,1);

% Preserve the client's first-step initialization.
Pd(1) = pv(1) - ld(1);
soc(1) = socmin;
imp(1) = -Pd(1);

% fminbnd with lb=0 normally evaluates interior points. Guard a numerically
% tiny candidate to avoid division by zero while retaining the same limit.
x_safe = max(double(x), eps);

for t = 2:nn
    Pd(t) = pv(t) - ld(t);
    E = Pd(t); % one-hour step, matching supplied MATLAB code

    if Pd(t) >= 0
        imp(t) = 0;
        if (soc(t-1) + ((E * effc) / x_safe)) < socmax
            soc(t) = soc(t-1) + ((E * effc) / x_safe);
        else
            soc(t) = socmax;
            exp_grid(t) = E - ((socmax - soc(t-1)) * x_safe / effc);
        end
    else
        if (soc(t-1) + Pd(t) / (x_safe * effb)) > socmin
            soc(t) = soc(t-1) - ((-Pd(t)) / (x_safe * effd * effb));
        else
            imp(t) = -Pd(t) - ((soc(t-1) - socmin) * x_safe * effb * effd);
            soc(t) = socmin;
        end
    end
end

Exp = sum(exp_grid);
Imp = sum(imp);
Losses = Imp - Exp;
Aab = x * Ab;
Aimp = Imp * rp;
Ar = Exp * fit;
f = Aab + Aimp - Ar;
end
