from datetime import timedelta
from uuid import UUID

from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calculations.artifact_access import resolve_artifact, resolve_artifact_object
from apps.calculations.models import Calculation, StoredCsvResult, StoredInputFile
from apps.feedback.models import Feedback
from apps.tariffs.models import TariffPlan
from .serializers import (
    AdminCalculationListSerializer,
    AdminCalculationSerializer,
    AdminFeedbackSerializer,
    AdminSummarySerializer,
    AdminTariffSerializer,
)


@extend_schema(tags=["Admin Dashboard"], responses={200: AdminSummarySerializer})
class AdminSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        qs = Calculation.objects.select_related("input_file", "csv_result").all()
        last7 = qs.filter(created_at__gte=now - timedelta(days=7))
        last30 = qs.filter(created_at__gte=now - timedelta(days=30))
        by_source = list(
            last30.values("source_mode")
            .annotate(count=Count("id"))
            .order_by("source_mode")
        )
        avg_runtime = last30.aggregate(v=Avg("runtime_ms"))["v"] or 0
        fb = Feedback.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).aggregate(count=Count("id"), avg=Avg("rating"))

        return Response(
            {
                "calculations": {
                    "today": qs.filter(created_at__date=timezone.localdate()).count(),
                    "last_7_days": last7.count(),
                    "last_30_days": last30.count(),
                    "all_time": qs.count(),
                },
                "source_modes": by_source,
                "average_runtime_ms": round(avg_runtime, 1),
                "feedback": {
                    "last_30_days": fb["count"],
                    "average_rating": round(fb["avg"], 2)
                    if fb["avg"] is not None
                    else None,
                },
                "recent": AdminCalculationListSerializer(qs[:10], many=True).data,
            }
        )


_ADMIN_LIST_PARAMETERS = [
    OpenApiParameter("status", str, description="Filter by processing/completed/failed."),
    OpenApiParameter("postcode", str, description="Exact postcode filter."),
    OpenApiParameter("state", str, description="Case-insensitive state filter."),
    OpenApiParameter("has_input", bool, description="Filter records with/without stored input bytes."),
    OpenApiParameter("has_csv", bool, description="Filter records with/without stored CSV bytes."),
    OpenApiParameter("q", str, description="Search postcode, suburb, state, filename, input SHA-256, or exact public UUID."),
]


@extend_schema(
    tags=["Admin Dashboard"],
    summary="List calculation records for the admin table",
    parameters=_ADMIN_LIST_PARAMETERS,
    responses={200: AdminCalculationListSerializer(many=True)},
)
class AdminCalculationListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminCalculationListSerializer
    queryset = Calculation.objects.select_related("input_file", "csv_result").all()

    def get_queryset(self):
        qs = super().get_queryset()

        status_value = self.request.query_params.get("status")
        if status_value in Calculation.Status.values:
            qs = qs.filter(status=status_value)

        postcode = (self.request.query_params.get("postcode") or "").strip()
        if postcode:
            qs = qs.filter(postcode=postcode)

        state_value = (self.request.query_params.get("state") or "").strip()
        if state_value:
            qs = qs.filter(state__iexact=state_value)

        has_input = self.request.query_params.get("has_input")
        if has_input in {"true", "1"}:
            qs = qs.filter(input_file__isnull=False)
        elif has_input in {"false", "0"}:
            qs = qs.filter(input_file__isnull=True)

        has_csv = self.request.query_params.get("has_csv")
        if has_csv in {"true", "1"}:
            qs = qs.filter(csv_result__isnull=False)
        elif has_csv in {"false", "0"}:
            qs = qs.filter(csv_result__isnull=True)

        query = (self.request.query_params.get("q") or "").strip()
        if query:
            search_q = (
                Q(postcode__icontains=query)
                | Q(suburb__icontains=query)
                | Q(state__icontains=query)
                | Q(input_payload__original_filename__icontains=query)
                | Q(input_payload__input_sha256__icontains=query)
            )
            try:
                search_q |= Q(public_id=UUID(query))
            except (ValueError, AttributeError):
                pass
            qs = qs.filter(search_q)

        return qs


@extend_schema(
    tags=["Admin Dashboard"],
    summary="View, update record metadata, or delete a calculation record",
    responses={200: AdminCalculationSerializer, 204: OpenApiResponse(description="Record deleted.")},
)
class AdminCalculationDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminCalculationSerializer
    queryset = Calculation.objects.select_related("input_file", "csv_result").all()
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"


@extend_schema(
    tags=["Admin Dashboard"],
    summary="Download a stored input or canonical CSV as an administrator",
    responses={200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Binary file download.")},
)
class AdminCalculationFileDownloadView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, public_id, file_id):
        calculation = get_object_or_404(
            Calculation.objects.select_related("input_file", "csv_result"), public_id=public_id
        )
        artifact = resolve_artifact(calculation, file_id)
        if artifact is None:
            raise Http404
        data, content_type, filename, size_bytes = artifact
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = content_disposition_header(True, filename)
        response["Content-Length"] = str(size_bytes)
        response["Cache-Control"] = "private, no-store"
        return response


@extend_schema(
    tags=["Admin Dashboard"],
    summary="Delete a stored input or CSV file without deleting calculation records",
    description=(
        "Deletes the selected stored file globally. Calculation records that referenced the file are retained and their "
        "file foreign key becomes null. Because unique input/CSV artifacts may be shared by several records, the response "
        "reports how many records were affected."
    ),
    responses={
        200: OpenApiResponse(description="File deleted; calculation records retained."),
        404: OpenApiResponse(description="File not found for this calculation."),
    },
)
class AdminCalculationFileDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, public_id, file_id):
        calculation = get_object_or_404(
            Calculation.objects.select_related("input_file", "csv_result"), public_id=public_id
        )
        artifact = resolve_artifact_object(calculation, file_id)
        if artifact is None:
            raise Http404

        if isinstance(artifact, StoredInputFile):
            kind = "input_workbook"
            filename = artifact.canonical_filename
            affected_records = artifact.calculations.count()
        elif isinstance(artifact, StoredCsvResult):
            kind = "legacy_csv"
            filename = artifact.filename
            affected_records = artifact.calculations.count()
        else:
            raise Http404

        artifact.delete()
        return Response(
            {
                "deleted": True,
                "kind": kind,
                "filename": filename,
                "affected_calculation_records": affected_records,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Admin Tariffs"])
class AdminTariffListCreateView(ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminTariffSerializer
    queryset = TariffPlan.objects.all()
    pagination_class = None


@extend_schema(tags=["Admin Tariffs"])
class AdminTariffDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminTariffSerializer
    queryset = TariffPlan.objects.all()


@extend_schema(tags=["Admin Feedback"])
class AdminFeedbackListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminFeedbackSerializer
    queryset = Feedback.objects.select_related("calculation").all().order_by("-created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        rating = self.request.query_params.get("rating")
        if rating and rating.isdigit():
            qs = qs.filter(rating=int(rating))
        return qs
