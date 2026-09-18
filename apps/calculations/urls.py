from django.urls import path
from .views import CalculationCreateView, CalculationDetailView, ClientWorkbookCalculationView

urlpatterns = [
    path("", CalculationCreateView.as_view(), name="calculation-create"),
    path("client-workbook/", ClientWorkbookCalculationView.as_view(), name="calculation-client-workbook"),
    path("<uuid:public_id>/", CalculationDetailView.as_view(), name="calculation-detail"),
]
