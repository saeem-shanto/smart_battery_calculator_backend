import hashlib
import secrets
import time
from uuid import UUID

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Calculation
from .serializers import (
    CalculationRequestSerializer,
    CalculationResponseSerializer,
    ClientWorkbookCalculationSerializer,
)
from .services.factory import get_engine
from .services.matlab_compiled import MatlabCompiledExecutionError, MatlabCompiledUnavailable
from .services.octave_engine import OctaveExecutionError, OctaveUnavailable
from .services.orchestration import build_engine_input
from .services.interfaces import EngineInput
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _response(obj, token):
    return {
        "public_id": obj.public_id,
        "access_token": token,
        "status": obj.status,
        "result": obj.result_payload,
        "assumptions": obj.assumptions,
        "warnings": obj.warnings,
        "algorithm_version": obj.algorithm_version,
        "runtime_ms": obj.runtime_ms,
        "created_at": obj.created_at,
    }


@extend_schema(
    tags=["Calculations"],
    request=CalculationRequestSerializer,
    responses={201: CalculationResponseSerializer},
)
class CalculationCreateView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "calculations"

    def post(self, request):
        serializer = CalculationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        start = time.perf_counter()

        try:
            engine = get_engine()
            data, assumptions, warnings = build_engine_input(serializer.validated_data)
            result = engine.calculate(data)
        except (MatlabCompiledUnavailable, OctaveUnavailable) as exc:
            return Response(
                {
                    "code": "calculation_engine_unavailable",
                    "detail": str(exc),
                    "engine": getattr(engine, "version", "unknown"),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (MatlabCompiledExecutionError, OctaveExecutionError) as exc:
            return Response(
                {
                    "code": "calculation_engine_failed",
                    "detail": str(exc),
                    "engine": getattr(engine, "version", "unknown"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as exc:
            raise ValidationError({"calculation": str(exc)}) from exc

        runtime = int((time.perf_counter() - start) * 1000)
        token = secrets.token_urlsafe(24)
        safe_input = {}
        for key, value in serializer.validated_data.items():
            safe_input[key] = str(value) if isinstance(value, UUID) else value

        obj = Calculation.objects.create(
            access_token_hash=_hash(token),
            status="completed",
            source_mode=serializer.validated_data["source_mode"],
            input_payload=safe_input,
            result_payload=result,
            assumptions=assumptions,
            warnings=warnings,
            algorithm_version=engine.version,
            runtime_ms=runtime,
        )
        return Response(_response(obj, token), status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Calculations"],
    request=ClientWorkbookCalculationSerializer,
    responses={201: CalculationResponseSerializer},
    description=(
        "Direct client-workbook calculation endpoint. Upload the legacy two-column workbook "
        "used by the supplied MATLAB workflow: column 1 = base PV profile, column 2 = load. "
        "The request is executed by the configured client-algorithm engine (GNU Octave by default)."
    ),
)
class ClientWorkbookCalculationView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "calculations"

    def post(self, request):
        serializer = ClientWorkbookCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attrs = serializer.validated_data
        upload = attrs["file"]

        try:
            workbook = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            raise ValidationError({"file": str(exc)}) from exc

        start = time.perf_counter()
        engine = get_engine()
        n = workbook.row_count
        data = EngineInput(
            load_kwh=workbook.load_profile,
            pv_kwh=workbook.pv_base_profile,
            interval_hours=1.0,
            import_rates=[float(attrs["retail_price_per_kwh"])] * n,
            feed_in_rates=[float(attrs["feed_in_tariff_per_kwh"])] * n,
            daily_supply_charge=0.0,
            demand_charge_rate_per_kw_day=0.0,
            battery_annual_cost_per_kwh=float(attrs["battery_annual_cost_per_kwh"]),
            battery_installed_cost_per_kwh=float(attrs["battery_installed_cost_per_kwh"]),
            max_capacity_kwh=float(attrs["max_battery_capacity_kwh"]),
            pv_size_kw=float(attrs["pv_size_kw"]),
            pv_profile_is_legacy_base=True,
        )

        assumptions = [
            "Client two-column workbook detected: column 1 is the legacy/base PV profile and column 2 is household load.",
            "Each workbook row is treated as one hour, matching the supplied MATLAB algorithm.",
            "The original PV scaling (1742.7/1737) × (PV size/3) is applied inside the MATLAB-compatible algorithm function.",
            "The optimization objective is the supplied client objective: battery annual payment + grid import cost - export FIT revenue.",
        ]
        warnings = list(workbook.warnings)

        try:
            result = engine.calculate(data)
        except (MatlabCompiledUnavailable, OctaveUnavailable) as exc:
            return Response(
                {
                    "code": "calculation_engine_unavailable",
                    "detail": str(exc),
                    "engine": getattr(engine, "version", "unknown"),
                    "file_validated": True,
                    "input_rows": workbook.row_count,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (MatlabCompiledExecutionError, OctaveExecutionError) as exc:
            return Response(
                {
                    "code": "calculation_engine_failed",
                    "detail": str(exc),
                    "engine": getattr(engine, "version", "unknown"),
                    "file_validated": True,
                    "input_rows": workbook.row_count,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        runtime = int((time.perf_counter() - start) * 1000)
        token = secrets.token_urlsafe(24)
        safe_input = {
            "original_name": upload.name,
            "detected_format": workbook.detected_format,
            "row_count": workbook.row_count,
            "pv_size_kw": float(attrs["pv_size_kw"]),
            "battery_annual_cost_per_kwh": float(attrs["battery_annual_cost_per_kwh"]),
            "battery_installed_cost_per_kwh": float(attrs["battery_installed_cost_per_kwh"]),
            "retail_price_per_kwh": float(attrs["retail_price_per_kwh"]),
            "feed_in_tariff_per_kwh": float(attrs["feed_in_tariff_per_kwh"]),
            "max_battery_capacity_kwh": float(attrs["max_battery_capacity_kwh"]),
            "raw_file_stored": False,
        }
        obj = Calculation.objects.create(
            access_token_hash=_hash(token),
            status="completed",
            source_mode="upload",
            input_payload=safe_input,
            result_payload=result,
            assumptions=assumptions,
            warnings=warnings,
            algorithm_version=engine.version,
            runtime_ms=runtime,
        )
        return Response(_response(obj, token), status=status.HTTP_201_CREATED)


@extend_schema(tags=["Calculations"], responses={200: CalculationResponseSerializer})
class CalculationDetailView(APIView):
    permission_classes = [AllowAny]

    def _check(self, request, obj):
        token = request.query_params.get("access_token") or request.headers.get("X-Calculation-Token")
        if not token or not secrets.compare_digest(_hash(token), obj.access_token_hash):
            raise PermissionDenied("A valid calculation access token is required.")
        return token

    def get(self, request, public_id):
        obj = get_object_or_404(Calculation, public_id=public_id)
        token = self._check(request, obj)
        return Response(_response(obj, token))

    def delete(self, request, public_id):
        obj = get_object_or_404(Calculation, public_id=public_id)
        self._check(request, obj)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
