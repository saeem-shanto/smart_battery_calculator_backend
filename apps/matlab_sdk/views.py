from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calculations.services.interfaces import EngineInput
from apps.calculations.services.matlab_compiled import (
    MatlabCompiledEngine,
    MatlabCompiledExecutionError,
    MatlabCompiledUnavailable,
)

from .serializers import MatlabSdkFileSerializer, MatlabSdkTestSerializer
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook


def _disabled_response():
    return Response(
        {
            "enabled": False,
            "detail": "MATLAB SDK test endpoints are disabled in this environment.",
        },
        status=status.HTTP_404_NOT_FOUND,
    )


def _run(attrs):
    engine = MatlabCompiledEngine()
    n = len(attrs["load_profile"])
    data = EngineInput(
        load_kwh=[float(x) for x in attrs["load_profile"]],
        pv_kwh=[float(x) for x in attrs["pv_profile"]],
        interval_hours=1.0,
        import_rates=[float(attrs["retail_price_per_kwh"])] * n,
        feed_in_rates=[float(attrs["feed_in_tariff_per_kwh"])] * n,
        daily_supply_charge=0.0,
        demand_charge_rate_per_kw_day=0.0,
        battery_annual_cost_per_kwh=float(attrs["battery_annual_cost_per_kwh"]),
        battery_installed_cost_per_kwh=float(attrs["battery_installed_cost_per_kwh"]),
        max_capacity_kwh=float(attrs["max_battery_capacity_kwh"]),
        pv_size_kw=float(attrs["pv_size_kw"]),
        pv_profile_is_legacy_base=bool(attrs["profile_is_base_pv"]),
    )
    return engine.calculate(data)


@extend_schema(tags=["MATLAB Compiler SDK"])
class MatlabSdkStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not settings.MATLAB_SDK_TEST_ENABLED:
            return _disabled_response()
        status_body = MatlabCompiledEngine().status()
        status_body["enabled"] = True
        status_body["calculation_engine"] = settings.CALCULATION_ENGINE
        http_status = status.HTTP_200_OK if status_body["runtime_ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(status_body, status=http_status)


@extend_schema(
    tags=["MATLAB Compiler SDK"],
    request=MatlabSdkTestSerializer,
    examples=[
        OpenApiExample(
            "24-hour legacy-style test",
            value={
                "pv_profile": [0,0,0,0,0,0.05,0.15,0.35,0.55,0.75,0.9,1.0,0.95,0.85,0.7,0.5,0.3,0.12,0.03,0,0,0,0,0],
                "load_profile": [0.35,0.3,0.28,0.26,0.3,0.4,0.55,0.6,0.5,0.4,0.35,0.3,0.32,0.35,0.4,0.5,0.75,1.1,1.3,1.0,0.8,0.65,0.5,0.4],
                "profile_is_base_pv": True,
                "pv_size_kw": 5,
                "battery_annual_cost_per_kwh": 50,
                "battery_installed_cost_per_kwh": 1000,
                "retail_price_per_kwh": 0.3773,
                "feed_in_tariff_per_kwh": 0.124,
                "max_battery_capacity_kwh": 50,
            },
            request_only=True,
        )
    ],
)
class MatlabSdkTestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "calculations"

    def post(self, request):
        if not settings.MATLAB_SDK_TEST_ENABLED:
            return _disabled_response()
        serializer = MatlabSdkTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = _run(serializer.validated_data)
        except MatlabCompiledUnavailable as exc:
            return Response({"code": "matlab_runtime_unavailable", "detail": str(exc)}, status=503)
        except MatlabCompiledExecutionError as exc:
            return Response({"code": "matlab_algorithm_failed", "detail": str(exc)}, status=502)
        return Response({"ok": True, "result": result})


@extend_schema(
    tags=["MATLAB Compiler SDK"],
    request=MatlabSdkFileSerializer,
    description=(
        "Upload the client two-column workbook directly. Column 1 is treated as the legacy/base PV profile "
        "and column 2 as load; the original PV scaling is applied inside compiled MATLAB."
    ),
)
class MatlabSdkFileTestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "uploads"

    def post(self, request):
        if not settings.MATLAB_SDK_TEST_ENABLED:
            return _disabled_response()
        serializer = MatlabSdkFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        try:
            workbook = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            return Response({"file": [str(exc)]}, status=400)

        attrs = dict(serializer.validated_data)
        attrs.pop("file", None)
        attrs["pv_profile"] = workbook.pv_base_profile
        attrs["load_profile"] = workbook.load_profile
        attrs["profile_is_base_pv"] = True
        try:
            result = _run(attrs)
        except MatlabCompiledUnavailable as exc:
            return Response(
                {
                    "code": "matlab_runtime_unavailable",
                    "detail": str(exc),
                    "file_validated": True,
                    "detected_format": workbook.detected_format,
                    "input_rows": workbook.row_count,
                    "warnings": workbook.warnings,
                },
                status=503,
            )
        except MatlabCompiledExecutionError as exc:
            return Response(
                {
                    "code": "matlab_algorithm_failed",
                    "detail": str(exc),
                    "file_validated": True,
                    "input_rows": workbook.row_count,
                },
                status=502,
            )
        return Response(
            {
                "ok": True,
                "detected_format": workbook.detected_format,
                "input_rows": workbook.row_count,
                "warnings": workbook.warnings,
                "result": result,
            }
        )

