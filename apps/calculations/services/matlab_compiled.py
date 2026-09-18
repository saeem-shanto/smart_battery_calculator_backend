from __future__ import annotations

import atexit
import importlib
import io
import platform
import sys
import threading
from dataclasses import asdict
from typing import Any

from django.conf import settings

from .interfaces import EngineInput


class MatlabCompiledUnavailable(RuntimeError):
    """Raised when the generated MATLAB Compiler SDK package cannot run."""


class MatlabCompiledExecutionError(RuntimeError):
    """Raised when the compiled MATLAB function fails during execution."""


def _flatten(value: Any) -> list[float]:
    """Convert MATLAB numeric containers / nested Python sequences to floats."""
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (str, bytes)):
        raise TypeError("MATLAB result unexpectedly contained text instead of numeric output.")

    # MATLAB numeric classes are iterable and may expose nested row lists.
    result: list[float] = []
    try:
        iterator = iter(value)
    except TypeError as exc:
        raise TypeError(f"Unsupported MATLAB result type: {type(value)!r}") from exc

    for item in iterator:
        if isinstance(item, (int, float)):
            result.append(float(item))
        else:
            result.extend(_flatten(item))
    return result


class MatlabCompiledEngine:
    """
    Calls a MATLAB Compiler SDK generated Python package in-process.

    The generated package is imported dynamically so this Django project can be
    installed before the compiled artifact exists. No Python implementation is
    silently used when this engine is selected.
    """

    version = "matlab-compiler-sdk-v1"

    _init_lock = threading.Lock()
    _call_lock = threading.Lock()
    _package_module = None
    _matlab_module = None
    _component = None
    _registered_atexit = False

    RESULT_FIELDS = (
        "optimal_battery_size_kwh",
        "net_annual_payment_aud",
        "export_to_grid_kwh_year",
        "import_from_grid_kwh_year",
        "energy_balance_import_minus_export_kwh_year",
        "average_retail_price_aud_per_kwh",
        "battery_annual_payment_rate_aud_per_kwh_year",
        "average_feed_in_tariff_aud_per_kwh",
        "pv_size_kw",
        "objective_value",
        "optimizer_exitflag",
        "baseline_annual_payment_aud",
        "estimated_annual_bill_reduction_aud",
        "estimated_annual_bill_reduction_percent",
        "battery_upfront_cost_aud",
        "simple_payback_years",
        "self_consumption_percent",
        "baseline_self_consumption_percent",
        "annual_load_kwh",
        "annual_pv_generation_kwh",
    )

    def __init__(self) -> None:
        self.package_name = settings.MATLAB_SDK_PACKAGE
        self.function_name = settings.MATLAB_SDK_FUNCTION

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._component = None
        cls._package_module = None
        cls._matlab_module = None

    @classmethod
    def _terminate(cls) -> None:
        component = cls._component
        cls._component = None
        if component is not None:
            try:
                component.terminate()
            except Exception:
                pass

    def _ensure_component(self):
        cls = type(self)
        if cls._component is not None:
            return cls._component

        with cls._init_lock:
            if cls._component is not None:
                return cls._component

            try:
                package = importlib.import_module(self.package_name)
            except Exception as exc:
                raise MatlabCompiledUnavailable(
                    f"Could not import compiled MATLAB package {self.package_name!r}. "
                    "Build it with MATLAB Compiler SDK and install the generated Python package "
                    "into this environment."
                ) from exc

            try:
                matlab = importlib.import_module("matlab")
            except Exception as exc:
                raise MatlabCompiledUnavailable(
                    "The MATLAB Python support module is unavailable. Install/use the generated "
                    "Compiler SDK package with the matching MATLAB Runtime environment."
                ) from exc

            # On Linux/server deployments, initialize_runtime can receive -nojvm/-nodisplay.
            # On macOS MathWorks requires running through mwpython; startup options passed here
            # are ignored, so do not pretend otherwise.
            try:
                if platform.system() != "Darwin" and settings.MATLAB_RUNTIME_OPTIONS:
                    package.initialize_runtime(list(settings.MATLAB_RUNTIME_OPTIONS))
                component = package.initialize()
            except Exception as exc:
                hint = ""
                if platform.system() == "Darwin":
                    hint = " On macOS run Django with MATLAB Runtime's mwpython executable."
                raise MatlabCompiledUnavailable(
                    "The compiled MATLAB package was found but MATLAB Runtime could not be "
                    f"initialized.{hint}"
                ) from exc

            cls._package_module = package
            cls._matlab_module = matlab
            cls._component = component
            if not cls._registered_atexit:
                atexit.register(cls._terminate)
                cls._registered_atexit = True
            return component

    def status(self) -> dict[str, Any]:
        package_importable = False
        matlab_module_importable = False
        package_error = None
        runtime_ready = False
        runtime_error = None

        try:
            importlib.import_module(self.package_name)
            package_importable = True
        except Exception as exc:
            package_error = f"{type(exc).__name__}: {exc}"

        try:
            importlib.import_module("matlab")
            matlab_module_importable = True
        except Exception:
            matlab_module_importable = False

        if package_importable and matlab_module_importable:
            try:
                self._ensure_component()
                runtime_ready = True
            except Exception as exc:
                runtime_error = f"{type(exc).__name__}: {exc}"

        return {
            "engine": self.version,
            "package_name": self.package_name,
            "function_name": self.function_name,
            "package_importable": package_importable,
            "matlab_module_importable": matlab_module_importable,
            "runtime_ready": runtime_ready,
            "package_error": package_error,
            "runtime_error": runtime_error,
            "python_executable": sys.executable,
            "platform": platform.system(),
            "runtime_options": list(settings.MATLAB_RUNTIME_OPTIONS),
        }

    def _vector(self, values: list[float]):
        matlab = type(self)._matlab_module
        if matlab is None:
            self._ensure_component()
            matlab = type(self)._matlab_module
        floats = [float(v) for v in values]
        return matlab.double(floats, size=(len(floats), 1))

    def _scalar(self, value: float):
        matlab = type(self)._matlab_module
        if matlab is None:
            self._ensure_component()
            matlab = type(self)._matlab_module
        return matlab.double([float(value)], size=(1, 1))

    def calculate(self, data: EngineInput) -> dict:
        if len(data.load_kwh) != len(data.pv_kwh) or not data.load_kwh:
            raise ValueError("Load and PV profiles must have the same non-zero length.")
        if abs(data.interval_hours - 1.0) > 1e-9:
            raise ValueError(
                "The compiled client algorithm expects hourly energy data. "
                "The orchestration layer must aggregate interval data to hourly values first."
            )
        if len(set(round(x, 10) for x in data.import_rates)) != 1:
            raise ValueError(
                "The client MATLAB algorithm supports one flat retail price per run; "
                "time-of-use rates cannot be silently averaged."
            )
        if len(set(round(x, 10) for x in data.feed_in_rates)) != 1:
            raise ValueError(
                "The client MATLAB algorithm supports one feed-in tariff per run."
            )
        if data.demand_charge_rate_per_kw_day > 0:
            raise ValueError(
                "Demand charges are not part of the supplied client MATLAB objective and "
                "cannot be used with the matlab_compiled engine."
            )

        component = self._ensure_component()
        function = getattr(component, self.function_name, None)
        if function is None:
            raise MatlabCompiledUnavailable(
                f"Compiled package {self.package_name!r} does not expose "
                f"{self.function_name!r}. Rebuild the package from matlab_sdk_source."
            )

        retail = float(data.import_rates[0])
        fit = float(data.feed_in_rates[0])
        stdout = io.StringIO()
        stderr = io.StringIO()

        args = (
            self._vector(data.pv_kwh),
            self._vector(data.load_kwh),
            self._scalar(data.pv_size_kw),
            self._scalar(data.battery_annual_cost_per_kwh),
            self._scalar(retail),
            self._scalar(fit),
            self._scalar(data.max_capacity_kwh),
            self._scalar(1.0 if data.pv_profile_is_legacy_base else 0.0),
            self._scalar(data.battery_installed_cost_per_kwh),
        )

        def invoke():
            try:
                raw = function(
                    *args,
                    nargout=1,
                    stdout=stdout,
                    stderr=stderr,
                )
            except Exception as exc:
                detail = stderr.getvalue().strip() or stdout.getvalue().strip()
                message = "Compiled MATLAB battery algorithm failed."
                if detail:
                    message += f" MATLAB output: {detail[-1500:]}"
                raise MatlabCompiledExecutionError(message) from exc
            return raw

        if settings.MATLAB_SERIALIZE_CALLS:
            with type(self)._call_lock:
                raw = invoke()
        else:
            raw = invoke()

        values = _flatten(raw)
        if len(values) < len(self.RESULT_FIELDS):
            raise MatlabCompiledExecutionError(
                f"MATLAB function returned {len(values)} values; "
                f"{len(self.RESULT_FIELDS)} are required by the v1 API contract."
            )

        parsed = dict(zip(self.RESULT_FIELDS, values[: len(self.RESULT_FIELDS)]))

        # Sentinel used by the MATLAB wrapper when payback is undefined.
        payback = parsed["simple_payback_years"]
        if payback < 0 or payback > 10_000:
            payback_value = None
        else:
            payback_value = round(payback, 2)

        result = {
            "optimal_battery_size_kwh": round(parsed["optimal_battery_size_kwh"], 3),
            "net_annual_payment_aud": round(parsed["net_annual_payment_aud"], 2),
            "baseline_annual_payment_aud": round(parsed["baseline_annual_payment_aud"], 2),
            "estimated_annual_bill_reduction_aud": round(parsed["estimated_annual_bill_reduction_aud"], 2),
            "estimated_annual_bill_reduction_percent": round(parsed["estimated_annual_bill_reduction_percent"], 2),
            "export_to_grid_kwh_year": round(parsed["export_to_grid_kwh_year"], 2),
            "import_from_grid_kwh_year": round(parsed["import_from_grid_kwh_year"], 2),
            "energy_balance_import_minus_export_kwh_year": round(parsed["energy_balance_import_minus_export_kwh_year"], 2),
            "annual_load_kwh": round(parsed["annual_load_kwh"], 2),
            "annual_pv_generation_kwh": round(parsed["annual_pv_generation_kwh"], 2),
            "self_consumption_percent": round(parsed["self_consumption_percent"], 2),
            "baseline_self_consumption_percent": round(parsed["baseline_self_consumption_percent"], 2),
            "battery_annual_payment_rate_aud_per_kwh_year": round(parsed["battery_annual_payment_rate_aud_per_kwh_year"], 3),
            "battery_upfront_cost_aud": round(parsed["battery_upfront_cost_aud"], 2),
            "simple_payback_years": payback_value,
            "average_retail_price_aud_per_kwh": round(parsed["average_retail_price_aud_per_kwh"], 5),
            "average_feed_in_tariff_aud_per_kwh": round(parsed["average_feed_in_tariff_aud_per_kwh"], 5),
            "annual_demand_charge_aud": 0.0,
            "pv_size_kw": round(parsed["pv_size_kw"], 3),
            "optimizer_success": parsed["optimizer_exitflag"] == 1,
            "optimizer_exitflag": int(round(parsed["optimizer_exitflag"])),
            "objective_value": round(parsed["objective_value"], 4),
            "engine": self.version,
            "algorithm_source": "compiled_matlab_client_algorithm",
            "profile_duration_hours": len(data.load_kwh),
            "profile_is_full_year": len(data.load_kwh) in {8760, 8784},
            "matlab_console": {
                "stdout": stdout.getvalue().strip(),
                "stderr": stderr.getvalue().strip(),
            },
            "matlab_compatible": {
                "battery_size_kwh": round(parsed["optimal_battery_size_kwh"], 3),
                "net_payment_aud_year": round(parsed["net_annual_payment_aud"], 2),
                "export_kwh_year": round(parsed["export_to_grid_kwh_year"], 2),
                "import_kwh_year": round(parsed["import_from_grid_kwh_year"], 2),
                "losses_legacy_import_minus_export_kwh_year": round(parsed["energy_balance_import_minus_export_kwh_year"], 2),
                "retail_price_aud_per_kwh": round(parsed["average_retail_price_aud_per_kwh"], 5),
                "battery_annual_payment_rate_aud_per_kwh_year": round(parsed["battery_annual_payment_rate_aud_per_kwh_year"], 3),
                "feed_in_tariff_aud_per_kwh": round(parsed["average_feed_in_tariff_aud_per_kwh"], 5),
                "pv_size_kw": round(parsed["pv_size_kw"], 3),
            },
        }
        return result
