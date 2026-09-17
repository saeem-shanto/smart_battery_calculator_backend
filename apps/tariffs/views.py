from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from .models import TariffPlan
from .serializers import TariffPlanSerializer

@extend_schema(tags=["Tariffs"])
class TariffListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = TariffPlanSerializer
    pagination_class = None
    def get_queryset(self):
        return TariffPlan.objects.filter(is_active=True)
