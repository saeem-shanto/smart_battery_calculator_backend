from django.urls import path
from .views import CalculationCreateView,CalculationDetailView
urlpatterns=[path("",CalculationCreateView.as_view(),name="calculation-create"),path("<uuid:public_id>/",CalculationDetailView.as_view(),name="calculation-detail")]
