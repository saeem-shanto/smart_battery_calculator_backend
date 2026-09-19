from django.urls import path

from .views import ClientWorkbookValidationView, ProfileUploadView

urlpatterns = [
    path("client-workbook/validate/", ClientWorkbookValidationView.as_view(), name="client-workbook-validate"),
    path("uploads/validate/", ProfileUploadView.as_view(), name="profile-upload"),
]
