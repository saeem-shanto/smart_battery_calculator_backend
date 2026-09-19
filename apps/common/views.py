import logging

from django.conf import settings
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.calculations.services.octave_engine import OctaveEngine

from .api_serializers import ApiRootResponseSerializer, HealthResponseSerializer, ReadinessResponseSerializer

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["System"],
    summary="API index",
    description="Human-readable discovery endpoint for the Smart Battery Calculator API.",
    responses={200: ApiRootResponseSerializer},
    operation_id="api_root",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def root(request):
    payload = {
        "name": "Smart Battery Calculator API",
        "status": "online",
        "api_version": "v1",
        "calculation_engine": settings.CALCULATION_ENGINE,
        "health": "/api/v1/health/",
        "readiness": "/api/v1/ready/",
        "swagger": "/api/docs/",
        "redoc": "/api/redoc/",
        "schema": "/api/schema/",
    }
    if settings.OCTAVE_DIAGNOSTICS_ENABLED:
        payload["octave_diagnostics"] = "/api/v1/octave/status/"
    return Response(payload)


@extend_schema(
    tags=["System"],
    summary="Liveness check",
    description="Cheap liveness check used by the hosting platform; it does not launch GNU Octave.",
    responses={200: HealthResponseSerializer},
    operation_id="health_liveness",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response(
        {
            "status": "ok",
            "service": "smart-battery-api",
            "calculation_engine": settings.CALCULATION_ENGINE,
            "time": timezone.now(),
        }
    )


@extend_schema(
    tags=["System"],
    summary="Readiness check",
    description="Checks the database and GNU Octave runtime/source availability.",
    responses={
        200: ReadinessResponseSerializer,
        503: OpenApiResponse(response=ReadinessResponseSerializer, description="A required component is not ready."),
    },
    operation_id="health_readiness",
)
@api_view(["GET"])
@permission_classes([AllowAny])
def readiness(request):
    database = {"ready": False, "detail": None}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database["ready"] = True
    except Exception as exc:  # pragma: no cover - environment specific
        logger.warning("Database readiness check failed: %s", type(exc).__name__)
        database["detail"] = "Database connection unavailable."

    raw = OctaveEngine().status()
    engine = {
        "ready": bool(raw.get("runtime_ready")),
        "engine": raw.get("engine"),
        "octave_version": raw.get("octave_version"),
        "algorithm_source_present": raw.get("algorithm_source_present"),
        "algorithm_sha256": raw.get("algorithm_sha256"),
        "detail": None if raw.get("runtime_ready") else "GNU Octave runtime or algorithm source unavailable.",
    }

    ready = bool(database["ready"] and engine["ready"])
    payload = {
        "status": "ready" if ready else "not_ready",
        "service": "smart-battery-api",
        "calculation_engine": settings.CALCULATION_ENGINE,
        "database": database,
        "engine": engine,
    }
    return Response(payload, status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)
