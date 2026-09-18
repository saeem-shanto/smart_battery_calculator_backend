% Build the deployable Python package used by Django.
% Requires MATLAB + MATLAB Compiler + MATLAB Compiler SDK.

here = fileparts(mfilename('fullpath'));
outDir = fullfile(here, 'build', 'smartbatterymatlab_python_package');
if ~exist(outDir, 'dir')
    mkdir(outDir);
end

buildResults = compiler.build.pythonPackage( ...
    fullfile(here, 'smart_battery_optimize.m'), ...
    'PackageName', 'smartbatterymatlab', ...
    'SampleGenerationFiles', fullfile(here, 'smart_battery_sample.m'), ...
    'OutputDir', outDir, ...
    'Verbose', 'on');

disp(buildResults);
fprintf('\nGenerated package folder:\n%s\n', outDir);
