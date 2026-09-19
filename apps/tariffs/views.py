from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from .models import TariffPlan
from .serializers import TariffPlanSerializer


@extend_schema(
    tags=["Tariffs"],
    summary="List active electricity tariffs",
    description=(
        "Returns tariff definitions available to the calculator. The client legacy Octave algorithm currently "
        "accepts flat retail/FIT rates only; incompatible tariff structures are rejected during calculation."
    ),
    responses={200: TariffPlanSerializer(many=True)},
    operation_id="tariff_list",
)
class TariffListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TariffPlanSerializer
    pagination_class = None

    def get_queryset(self):
        return TariffPlan.objects.filter(is_active=True)
