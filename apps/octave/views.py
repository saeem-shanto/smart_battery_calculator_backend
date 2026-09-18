from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calculations.services.interfaces import EngineInput
from apps.calculations.services.octave_engine import (
    OctaveEngine,
    OctaveExecutionError,
    OctaveUnavailable,
)
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook

from .serializers import OctaveFileSerializer, OctaveTestSerializer


def _disabled_response():
    return Response(
        {"enabled": False, "detail": "GNU Octave test endpoints are disabled in this environment."},
        status=status.HTTP_404_NOT_FOUND,
    )


def _run(attrs):
    engine = OctaveEngine()
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


@extend_schema(tags=["GNU Octave"])
class OctaveStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not settings.OCTAVE_TEST_ENABLED:
            return _disabled_response()
        body = OctaveEngine().status()
        body["enabled"] = True
        body["calculation_engine"] = settings.CALCULATION_ENGINE
        http_status = status.HTTP_200_OK if body["runtime_ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(body, status=http_status)


@extend_schema(
    tags=["GNU Octave"],
    request=OctaveTestSerializer,
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
class OctaveTestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "calculations"

    def post(self, request):
        if not settings.OCTAVE_TEST_ENABLED:
            return _disabled_response()
        serializer = OctaveTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = _run(serializer.validated_data)
        except OctaveUnavailable as exc:
            return Response({"code": "octave_unavailable", "detail": str(exc)}, status=503)
        except OctaveExecutionError as exc:
            return Response({"code": "octave_algorithm_failed", "detail": str(exc)}, status=502)
        return Response({"ok": True, "result": result})


@extend_schema(
    tags=["GNU Octave"],
    request=OctaveFileSerializer,
    description=(
        "Upload the client two-column workbook directly. Column 1 is the legacy/base PV profile "
        "and column 2 is load; the original algorithm is executed by GNU Octave."
    ),
)
class OctaveFileTestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "uploads"

    def post(self, request):
        if not settings.OCTAVE_TEST_ENABLED:
            return _disabled_response()
        serializer = OctaveFileSerializer(data=request.data)
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
        except OctaveUnavailable as exc:
            return Response(
                {
                    "code": "octave_unavailable",
                    "detail": str(exc),
                    "file_validated": True,
                    "detected_format": workbook.detected_format,
                    "input_rows": workbook.row_count,
                    "warnings": workbook.warnings,
                },
                status=503,
            )
        except OctaveExecutionError as exc:
            return Response(
                {
                    "code": "octave_algorithm_failed",
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
