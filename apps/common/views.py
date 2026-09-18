from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(tags=["System"], responses={200: dict})
@api_view(["GET"])
@permission_classes([AllowAny])
def root(request):
    return Response(
        {
            "name": "Smart Battery Calculator API",
            "status": "online",
            "calculation_engine": settings.CALCULATION_ENGINE,
            "health": "/api/v1/health/",
            "swagger": "/api/docs/",
            "redoc": "/api/redoc/",
        }
    )


@extend_schema(tags=["System"], responses={200: dict})
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
