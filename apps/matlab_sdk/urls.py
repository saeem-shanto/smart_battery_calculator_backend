from django.urls import path

from .views import MatlabSdkFileTestView, MatlabSdkStatusView, MatlabSdkTestView

urlpatterns = [
    path("status/", MatlabSdkStatusView.as_view(), name="matlab-sdk-status"),
    path("test/", MatlabSdkTestView.as_view(), name="matlab-sdk-test"),
    path("test-file/", MatlabSdkFileTestView.as_view(), name="matlab-sdk-test-file"),
]
