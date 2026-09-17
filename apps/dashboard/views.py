from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.calculations.models import Calculation
from apps.feedback.models import Feedback
from apps.tariffs.models import TariffPlan
from .serializers import AdminTariffSerializer, AdminFeedbackSerializer


class AdminCalculationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calculation
        fields = [
            "public_id",
            "status",
            "source_mode",
            "input_payload",
            "result_payload",
            "assumptions",
            "warnings",
            "algorithm_version",
            "runtime_ms",
            "created_at",
        ]


@extend_schema(tags=["Admin Dashboard"], responses={200: dict})
class AdminSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        qs = Calculation.objects.all()
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
                "recent": AdminCalculationSerializer(qs[:10], many=True).data,
            }
        )


@extend_schema(tags=["Admin Dashboard"])
class AdminCalculationListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminCalculationSerializer
    queryset = Calculation.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        mode = self.request.query_params.get("source_mode")
        if mode in {"simplified", "upload"}:
            qs = qs.filter(source_mode=mode)
        return qs


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
