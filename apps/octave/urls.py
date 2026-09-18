from django.urls import path

from .views import OctaveFileTestView, OctaveStatusView, OctaveTestView

urlpatterns = [
    path("status/", OctaveStatusView.as_view(), name="octave-status"),
    path("test/", OctaveTestView.as_view(), name="octave-test"),
    path("test-file/", OctaveFileTestView.as_view(), name="octave-test-file"),
]
