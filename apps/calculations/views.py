from __future__ import annotations

import hashlib
import mimetypes
import secrets
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api_exceptions import BadGateway, ServiceUnavailable
from apps.common.api_serializers import ApiErrorSerializer
from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook

from .artifact_access import calculation_artifacts, resolve_artifact
from .models import Calculation, StoredCsvResult, StoredInputFile
from .serializers import (
    CalculationCreateResponseSerializer,
    CalculationDetailResponseSerializer,
    CalculationFileSerializer,
    ClientWorkbookCalculationSerializer,
)
from .services.errors import CalculationEngineExecutionError, CalculationEngineUnavailable
from .services.executor import execute_calculation
from .services.input_builders import build_client_workbook_engine_input
from .services.result_cache import apply_reporting_cost, canonicalize_algorithm_result
from .services.result_contract import validate_result_contract


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_filename(name: str) -> str:
    return Path(name or "upload.bin").name[:255]


def _response(obj: Calculation, token: str | None = None) -> dict:
    input_filename = (obj.input_payload or {}).get("original_filename")
    if not input_filename and obj.input_file_id:
        input_filename = obj.input_file.canonical_filename
    payload = {
        "public_id": obj.public_id,
        "status": obj.status,
        "postcode": obj.postcode,
        "suburb": obj.suburb,
        "state": obj.state,
        "metadata": obj.metadata,
        "input_filename": input_filename,
        "result": obj.result_payload,
        "assumptions": obj.assumptions,
        "warnings": obj.warnings,
        "algorithm_version": obj.algorithm_version,
        "runtime_ms": obj.runtime_ms,
        "files": calculation_artifacts(obj),
        "created_at": obj.created_at,
    }
    if token is not None:
        payload["access_token"] = token
    return payload


def _no_store(response):
    response["Cache-Control"] = "no-store"
    return response


def _check_access(request, obj: Calculation) -> None:
    token = request.headers.get("X-Calculation-Token")
    if not token or not secrets.compare_digest(_hash(token), obj.access_token_hash):
        raise PermissionDenied("A valid X-Calculation-Token header is required.")


def _translate_engine_error(exc: Exception):
    if isinstance(exc, CalculationEngineUnavailable):
        raise ServiceUnavailable(
            "The battery calculation service is temporarily unavailable.",
            code="calculation_engine_unavailable",
        ) from exc
    if isinstance(exc, CalculationEngineExecutionError):
        raise BadGateway(
            "The battery calculation engine could not complete this request.",
            code="calculation_engine_failed",
        ) from exc
    raise exc


def _get_or_store_input(*, raw_input: bytes, original_filename: str, content_type: str, workbook) -> StoredInputFile:
    digest = _sha256(raw_input)
    stored, _created = StoredInputFile.objects.get_or_create(
        sha256=digest,
        defaults={
            "canonical_filename": original_filename,
            "content_type": content_type,
            "size_bytes": len(raw_input),
            "data": raw_input,
            "detected_format": workbook.detected_format,
            "row_count": workbook.row_count,
            "parsing_warnings": list(workbook.warnings or []),
        },
    )
    return stored


@extend_schema(
    tags=["Calculations"],
    summary="Run the original client MATLAB workbook calculation",
    description=(
        "Executes the client's unchanged battrail.m and natpaymenttrail.m under GNU Octave. "
        "Input files are deduplicated by SHA-256. Each unique input file is stored once and has at most one canonical "
        "Results_RPAtrail400.csv. Re-uploading identical bytes reuses the stored CSV instead of generating another copy. "
        "The source fixes PV size=5 kW, battery annual rate=50 AUD/kWh/year, retail=0.3773 AUD/kWh, "
        "FiT=0.124 AUD/kWh and battery search range=0-50 kWh."
    ),
    request=ClientWorkbookCalculationSerializer,
    responses={
        201: CalculationCreateResponseSerializer,
        400: ApiErrorSerializer,
        502: ApiErrorSerializer,
        503: ApiErrorSerializer,
    },
    operation_id="calculation_client_workbook",
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

        raw_input = upload.read()
        if hasattr(upload, "seek"):
            upload.seek(0)
        original_filename = _safe_filename(upload.name)
        if not raw_input:
            raise ValidationError({"file": "The uploaded file is empty."})

        try:
            workbook = parse_client_workbook(upload)
        except ClientWorkbookError as exc:
            raise ValidationError({"file": str(exc)}) from exc

        if settings.REQUIRE_FULL_YEAR_PROFILE and workbook.row_count not in {8760, 8784}:
            raise ValidationError(
                {"file": "A production calculation requires a complete 8760-hour year (8784 for leap years)."}
            )

        data, assumptions, warnings = build_client_workbook_engine_input(workbook, attrs)
        token = secrets.token_urlsafe(32)
        content_type = (
            getattr(upload, "content_type", "")
            or mimetypes.guess_type(original_filename)[0]
            or "application/octet-stream"
        )

        try:
            with transaction.atomic():
                stored_input = _get_or_store_input(
                    raw_input=raw_input,
                    original_filename=original_filename,
                    content_type=content_type,
                    workbook=workbook,
                )
                cached_csv = StoredCsvResult.objects.filter(
                    source_input_sha256=stored_input.sha256
                ).first()
                if cached_csv is not None and cached_csv.input_file_id is None:
                    cached_csv.input_file = stored_input
                    cached_csv.save(update_fields=["input_file"])
                calculation = Calculation.objects.create(
                    access_token_hash=_hash(token),
                    input_file=stored_input,
                    csv_result=cached_csv,
                    postcode=attrs.get("postcode", ""),
                    suburb=attrs.get("suburb", ""),
                    state=attrs.get("state", ""),
                    metadata=attrs.get("metadata", {}) or {},
                    status=Calculation.Status.PROCESSING,
                    source_mode=Calculation.SourceMode.UPLOAD,
                    input_payload={
                        "original_filename": original_filename,
                        "detected_format": workbook.detected_format,
                        "row_count": workbook.row_count,
                        "battery_installed_cost_per_kwh": float(attrs["battery_installed_cost_per_kwh"]),
                        "input_sha256": stored_input.sha256,
                        "stored_input_id": str(stored_input.id),
                        "csv_reused": bool(cached_csv),
                        "legacy_runtime_input_filename": "Vanikavipuldata.xls",
                        "legacy_output_filename": "Results_RPAtrail400.csv",
                    },
                    assumptions=assumptions,
                    warnings=warnings,
                )
        except Exception as exc:
            raise APIException("The uploaded file could not be persisted for calculation.") from exc

        # One unique input -> one canonical CSV. If it already exists, reuse it.
        if cached_csv is not None:
            try:
                result = apply_reporting_cost(
                    cached_csv.result_payload,
                    float(attrs["battery_installed_cost_per_kwh"]),
                )
                result = validate_result_contract(result, data)
            except Exception as exc:
                calculation.status = Calculation.Status.FAILED
                calculation.error_code = "cached_result_invalid"
                calculation.error_message = f"{type(exc).__name__}: {exc}"[:4000]
                calculation.save(update_fields=["status", "error_code", "error_message", "updated_at"])
                raise APIException("The stored calculation result could not be reused safely.") from exc

            calculation.status = Calculation.Status.COMPLETED
            calculation.result_payload = result
            calculation.csv_result = cached_csv
            calculation.algorithm_version = cached_csv.engine_version
            calculation.runtime_ms = 0
            calculation.save(
                update_fields=[
                    "status", "result_payload", "csv_result", "algorithm_version", "runtime_ms", "updated_at"
                ]
            )
            return _no_store(Response(_response(calculation, token), status=status.HTTP_201_CREATED))

        try:
            execution = execute_calculation(data)
        except (CalculationEngineUnavailable, CalculationEngineExecutionError) as exc:
            calculation.status = Calculation.Status.FAILED
            calculation.error_code = type(exc).__name__[:80]
            calculation.error_message = str(exc)[:4000]
            calculation.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            _translate_engine_error(exc)
        except ValueError as exc:
            calculation.status = Calculation.Status.FAILED
            calculation.error_code = "invalid_calculation_input"
            calculation.error_message = str(exc)[:4000]
            calculation.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            raise ValidationError({"calculation": str(exc)}) from exc

        legacy_csv = execution.artifacts.get("Results_RPAtrail400.csv")
        if not legacy_csv:
            calculation.status = Calculation.Status.FAILED
            calculation.error_code = "missing_legacy_csv"
            calculation.error_message = "The calculation completed without the required legacy CSV artifact."
            calculation.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            raise BadGateway(
                "The battery calculation engine did not produce its required CSV output.",
                code="missing_legacy_csv",
            )

        canonical_result = canonicalize_algorithm_result(execution.result)
        try:
            csv_result, created = StoredCsvResult.objects.get_or_create(
                source_input_sha256=stored_input.sha256,
                defaults={
                    "input_file": stored_input,
                    "filename": "Results_RPAtrail400.csv",
                    "content_type": "text/csv",
                    "size_bytes": len(legacy_csv),
                    "sha256": _sha256(legacy_csv),
                    "data": legacy_csv,
                    "result_payload": canonical_result,
                    "engine_version": execution.engine_version,
                    "algorithm_sha256": str(execution.result.get("algorithm_sha256") or ""),
                    "runtime_ms": execution.runtime_ms,
                },
            )
        except Exception as exc:
            calculation.status = Calculation.Status.FAILED
            calculation.error_code = "legacy_csv_persistence_failed"
            calculation.error_message = f"{type(exc).__name__}: {exc}"[:4000]
            calculation.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            raise APIException("The calculation completed but its legacy CSV could not be persisted.") from exc

        # A concurrent request may have created the canonical CSV first. In that
        # case, use the already-stored canonical result rather than creating a duplicate.
        result = execution.result if created else apply_reporting_cost(
            csv_result.result_payload,
            float(attrs["battery_installed_cost_per_kwh"]),
        )
        result = validate_result_contract(result, data)

        if csv_result.input_file_id is None:
            csv_result.input_file = stored_input
            csv_result.save(update_fields=["input_file"])

        calculation.status = Calculation.Status.COMPLETED
        calculation.result_payload = result
        calculation.csv_result = csv_result
        calculation.algorithm_version = csv_result.engine_version
        calculation.runtime_ms = execution.runtime_ms if created else 0
        payload = dict(calculation.input_payload or {})
        payload["csv_reused"] = not created
        calculation.input_payload = payload
        calculation.error_code = ""
        calculation.error_message = ""
        calculation.save(
            update_fields=[
                "status",
                "result_payload",
                "csv_result",
                "algorithm_version",
                "runtime_ms",
                "input_payload",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )

        return _no_store(Response(_response(calculation, token), status=status.HTTP_201_CREATED))


_ACCESS_TOKEN_PARAMETER = [
    OpenApiParameter(
        name="X-Calculation-Token",
        type=str,
        location=OpenApiParameter.HEADER,
        required=True,
        description="Private token returned once when the calculation is created.",
    )
]


class CalculationDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Calculations"],
        summary="Retrieve a calculation and its currently available file list",
        parameters=_ACCESS_TOKEN_PARAMETER,
        responses={200: CalculationDetailResponseSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer},
        operation_id="calculation_retrieve",
    )
    def get(self, request, public_id):
        obj = get_object_or_404(Calculation.objects.select_related("input_file", "csv_result"), public_id=public_id)
        _check_access(request, obj)
        return _no_store(Response(_response(obj)))

    @extend_schema(
        tags=["Calculations"],
        summary="Delete a calculation record",
        description=(
            "Deletes this calculation record. Content-addressed input/CSV artifacts are retained while any other "
            "calculation references the same unique input and are cleaned up when orphaned by the maintenance command."
        ),
        parameters=_ACCESS_TOKEN_PARAMETER,
        responses={204: OpenApiResponse(description="Calculation deleted."), 403: ApiErrorSerializer, 404: ApiErrorSerializer},
        operation_id="calculation_delete",
    )
    def delete(self, request, public_id):
        obj = get_object_or_404(Calculation, public_id=public_id)
        _check_access(request, obj)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Calculations"],
    summary="List the stored input and canonical CSV",
    description="A completed calculation can expose up to two files: the unique input and its canonical Results_RPAtrail400.csv. Either may be absent if an administrator deleted the stored bytes.",
    parameters=_ACCESS_TOKEN_PARAMETER,
    responses={200: CalculationFileSerializer(many=True), 403: ApiErrorSerializer, 404: ApiErrorSerializer},
    operation_id="calculation_files_list",
)
class CalculationFileListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        obj = get_object_or_404(Calculation.objects.select_related("input_file", "csv_result"), public_id=public_id)
        _check_access(request, obj)
        return _no_store(Response(calculation_artifacts(obj)))


@extend_schema(
    tags=["Calculations"],
    summary="Download the unique input file or its canonical CSV",
    parameters=_ACCESS_TOKEN_PARAMETER,
    responses={200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Binary file download."), 403: ApiErrorSerializer, 404: ApiErrorSerializer},
    operation_id="calculation_file_download",
)
class CalculationFileDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id, file_id):
        calculation = get_object_or_404(Calculation.objects.select_related("input_file", "csv_result"), public_id=public_id)
        _check_access(request, calculation)
        artifact = resolve_artifact(calculation, file_id)
        if artifact is None:
            raise Http404
        data, content_type, filename, size_bytes = artifact
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = content_disposition_header(True, filename)
        response["Content-Length"] = str(size_bytes)
        return _no_store(response)
