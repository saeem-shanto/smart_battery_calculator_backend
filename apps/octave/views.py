from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calculations.services.errors import CalculationEngineExecutionError, CalculationEngineUnavailable
from apps.calculations.services.executor import execute_calculation
from apps.calculations.services.input_builders import build_client_workbook_engine_input, build_direct_engine_input
from apps.calculations.services.octave_engine import OctaveEngine
from apps.common.api_exceptions import BadGateway, ServiceUnavailable
from apps.common.api_serializers import ApiErrorSerializer
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook

from .serializers import (
    OctaveFileSerializer,
    OctaveFileTestResponseSerializer,
    OctaveStatusSerializer,
    OctaveTestResponseSerializer,
    OctaveTestSerializer,
)


def _ensure_enabled() -> None:
    if not settings.OCTAVE_DIAGNOSTICS_ENABLED:
        raise NotFound("GNU Octave diagnostic endpoints are disabled in this environment.")


def _translate_engine_error(exc: Exception):
    if isinstance(exc, CalculationEngineUnavailable):
        raise ServiceUnavailable(str(exc), code="octave_unavailable") from exc
    if isinstance(exc, CalculationEngineExecutionError):
        raise BadGateway(str(exc), code="octave_algorithm_failed") from exc
    raise exc


class OctaveStatusView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["GNU Octave diagnostics"],
        summary="Check GNU Octave and immutable MATLAB source status",
        responses={200: OctaveStatusSerializer, 503: OctaveStatusSerializer, 404: ApiErrorSerializer},
        operation_id="octave_status",
    )
    def get(self, request):
        _ensure_enabled()
        body = OctaveEngine().status()
        body["enabled"] = True
        body["calculation_engine"] = settings.CALCULATION_ENGINE
        return Response(body, status=status.HTTP_200_OK if body["runtime_ready"] else status.HTTP_503_SERVICE_UNAVAILABLE)


class OctaveTestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "diagnostics"

    @extend_schema(
        tags=["GNU Octave diagnostics"],
        summary="Run unchanged MATLAB source from diagnostic arrays",
        description="The arrays are treated as the same legacy base-PV/load columns expected by Vanikavipuldata.xls.",
        request=OctaveTestSerializer,
        responses={200: OctaveTestResponseSerializer, 400: ApiErrorSerializer, 404: ApiErrorSerializer, 502: ApiErrorSerializer, 503: ApiErrorSerializer},
        operation_id="octave_direct_test",
        examples=[OpenApiExample(
            "24-hour legacy-style test",
            request_only=True,
            value={
                "pv_profile": [0,0,0,0,0,0.05,0.15,0.35,0.55,0.75,0.9,1,0.95,0.85,0.7,0.5,0.3,0.12,0.03,0,0,0,0,0],
                "load_profile": [0.35,0.3,0.28,0.26,0.3,0.4,0.55,0.6,0.5,0.4,0.35,0.3,0.32,0.35,0.4,0.5,0.75,1.1,1.3,1,0.8,0.65,0.5,0.4],
                "battery_installed_cost_per_kwh": 1000,
            },
        )],
    )
    def post(self, request):
        _ensure_enabled()
        serializer = OctaveTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = build_direct_engine_input(serializer.validated_data)
        try:
            execution = execute_calculation(data)
        except (CalculationEngineUnavailable, CalculationEngineExecutionError) as exc:
            _translate_engine_error(exc)
        return Response({"ok": True, "runtime_ms": execution.runtime_ms, "result": execution.result})


class OctaveFileTestView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "diagnostics"

    @extend_schema(
        tags=["GNU Octave diagnostics"],
        summary="Run unchanged MATLAB source from a client workbook without saving it",
        request=OctaveFileSerializer,
        responses={200: OctaveFileTestResponseSerializer, 400: ApiErrorSerializer, 404: ApiErrorSerializer, 502: ApiErrorSerializer, 503: ApiErrorSerializer},
        operation_id="octave_workbook_test",
    )
    def post(self, request):
        _ensure_enabled()
        serializer = OctaveFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        try:
            workbook = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            raise ValidationError({"file": str(exc)}) from exc

        data, _, warnings = build_client_workbook_engine_input(workbook, serializer.validated_data)
        try:
            execution = execute_calculation(data)
        except (CalculationEngineUnavailable, CalculationEngineExecutionError) as exc:
            _translate_engine_error(exc)
        return Response({
            "ok": True,
            "runtime_ms": execution.runtime_ms,
            "detected_format": workbook.detected_format,
            "input_rows": workbook.row_count,
            "warnings": warnings,
            "result": execution.result,
        })
