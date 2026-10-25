from django.urls import path
from .generated_views import GenerateAnnualProfileView, GeneratedAnnualCalculationView

from .views import (
    CalculationDetailView,
    CalculationFileDownloadView,
    CalculationFileListView,
    CalculationClaimView,
    ClientWorkbookCalculationView,
)

urlpatterns = [
    path("generated-annual/", GeneratedAnnualCalculationView.as_view(), name="calculation-generated-annual"),
    path("generate-annual-profile/", GenerateAnnualProfileView.as_view(), name="generate-annual-profile"),
    path("client-workbook/", ClientWorkbookCalculationView.as_view(), name="calculation-client-workbook"),
    path("<uuid:public_id>/", CalculationDetailView.as_view(), name="calculation-detail"),
    path("<uuid:public_id>/claim/", CalculationClaimView.as_view(), name="calculation-claim"),
    path("<uuid:public_id>/files/", CalculationFileListView.as_view(), name="calculation-files"),
    path(
        "<uuid:public_id>/files/<uuid:file_id>/download/",
        CalculationFileDownloadView.as_view(),
        name="calculation-file-download",
    ),
]
