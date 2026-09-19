function data = xlsread(filename)
%XLSREAD Compatibility shim used only by the Django runtime bridge.
% The immutable client MATLAB files remain unchanged. Django writes the parsed
% numeric input into the legacy expected filename in a temporary directory.
data = dlmread(filename, ',');
end
