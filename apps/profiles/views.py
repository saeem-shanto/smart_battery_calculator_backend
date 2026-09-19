from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api_serializers import ApiErrorSerializer

from .client_workbook import ClientWorkbookError, parse_client_workbook
from .models import ProfileUpload
from .parsers import ProfileParseError, parse_profile_file
from .serializers import (
    ClientWorkbookValidationResponseSerializer,
    ClientWorkbookValidationSerializer,
    ProfileUploadResponseSerializer,
    ProfileUploadSerializer,
)


class ClientWorkbookValidationView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "uploads"

    @extend_schema(
        tags=["Profile Uploads"],
        summary="Validate a client workbook without retaining it",
        description=(
            "Parses the exact workbook convention used by the immutable MATLAB/Octave workflow and validates the "
            "production full-year requirement. This endpoint is privacy-safe: it does not create database rows and does "
            "not retain uploaded bytes or parsed household values after the request completes."
        ),
        request=ClientWorkbookValidationSerializer,
        responses={200: ClientWorkbookValidationResponseSerializer, 400: ApiErrorSerializer},
        operation_id="client_workbook_validate_transient",
    )
    def post(self, request):
        serializer = ClientWorkbookValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        try:
            workbook = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc

        if settings.REQUIRE_FULL_YEAR_PROFILE and workbook.row_count not in {8760, 8784}:
            raise ValidationError(
                {
                    "file": [
                        "A production calculation requires a complete 8760-hour year (8784 for leap years). "
                        f"This file contains {workbook.row_count} usable rows."
                    ]
                }
            )

        return Response(
            {
                "valid": True,
                "original_name": upload.name,
                "detected_format": workbook.detected_format,
                "row_count": workbook.row_count,
                "profile_is_full_year": workbook.row_count in {8760, 8784},
                "warnings": list(workbook.warnings or []),
            },
            status=status.HTTP_200_OK,
        )


class ProfileUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "uploads"

    @extend_schema(
        tags=["Profile Uploads"],
        summary="Validate and stage an interval profile",
        description=(
            "Validates a load/PV profile and stores only its parsed normalized payload for a limited time. "
            "This legacy staging endpoint is separate from the privacy-safe client workbook validation endpoint."
        ),
        request=ProfileUploadSerializer,
        responses={201: ProfileUploadResponseSerializer, 400: ApiErrorSerializer},
        operation_id="profile_upload_validate",
    )
    def post(self, request):
        ProfileUpload.objects.filter(expires_at__lte=timezone.now()).delete()
        serializer = ProfileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        max_bytes = settings.PROFILE_UPLOAD_MAX_MB * 1024 * 1024
        if upload.size > max_bytes:
            raise ValidationError(
                {"file": [f"File exceeds the {settings.PROFILE_UPLOAD_MAX_MB} MB limit."]}
            )

        try:
            parsed = parse_profile_file(
                upload,
                serializer.validated_data["data_role"],
                serializer.validated_data["value_kind"],
                serializer.validated_data.get("interval_minutes"),
            )
        except ProfileParseError as exc:
            raise ValidationError({"file": [str(exc)]}) from exc

        payload = {
            "load_values": parsed.load_values,
            "pv_values": parsed.pv_values,
            "timestamps": parsed.timestamps,
        }
        count = len(parsed.load_values or parsed.pv_values or [])
        obj = ProfileUpload.objects.create(
            role=serializer.validated_data["data_role"],
            original_name=upload.name,
            detected_format=parsed.detected_format,
            interval_minutes=parsed.interval_minutes,
            value_kind=parsed.value_kind,
            parsed_payload=payload,
            warnings=parsed.warnings,
            row_count=count,
            expires_at=timezone.now()
            + timedelta(hours=settings.PROFILE_UPLOAD_TTL_HOURS),
        )
        return Response(
            {
                "upload_token": obj.id,
                "original_name": obj.original_name,
                "detected_format": obj.detected_format,
                "data_role": obj.role,
                "interval_minutes": obj.interval_minutes,
                "value_kind": obj.value_kind,
                "interval_count": obj.row_count,
                "warnings": obj.warnings,
                "expires_at": obj.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )
