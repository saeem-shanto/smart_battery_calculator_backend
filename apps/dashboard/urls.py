from django.urls import path

from .views import (
    AdminCalculationDetailView,
    AdminCalculationFileDeleteView,
    AdminCalculationFileDownloadView,
    AdminCalculationListView,
    AdminFeedbackListView,
    AdminSummaryView,
    AdminTariffDetailView,
    AdminTariffListCreateView,
)

urlpatterns = [
    path("summary/", AdminSummaryView.as_view(), name="admin-summary"),
    path("calculations/", AdminCalculationListView.as_view(), name="admin-calculations"),
    path(
        "calculations/<uuid:public_id>/",
        AdminCalculationDetailView.as_view(),
        name="admin-calculation-detail",
    ),
    path(
        "calculations/<uuid:public_id>/files/<uuid:file_id>/",
        AdminCalculationFileDeleteView.as_view(),
        name="admin-calculation-file-delete",
    ),
    path(
        "calculations/<uuid:public_id>/files/<uuid:file_id>/download/",
        AdminCalculationFileDownloadView.as_view(),
        name="admin-calculation-file-download",
    ),
    path("feedback/", AdminFeedbackListView.as_view(), name="admin-feedback"),
    path("tariffs/", AdminTariffListCreateView.as_view(), name="admin-tariffs"),
    path("tariffs/<uuid:pk>/", AdminTariffDetailView.as_view(), name="admin-tariff-detail"),
]
