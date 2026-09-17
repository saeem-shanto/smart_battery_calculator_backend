from django.urls import path

from .views import (
    AdminCalculationListView,
    AdminFeedbackListView,
    AdminSummaryView,
    AdminTariffDetailView,
    AdminTariffListCreateView,
)

urlpatterns = [
    path("summary/", AdminSummaryView.as_view(), name="admin-summary"),
    path("calculations/", AdminCalculationListView.as_view(), name="admin-calculations"),
    path("feedback/", AdminFeedbackListView.as_view(), name="admin-feedback"),
    path("tariffs/", AdminTariffListCreateView.as_view(), name="admin-tariffs"),
    path("tariffs/<uuid:pk>/", AdminTariffDetailView.as_view(), name="admin-tariff-detail"),
]
