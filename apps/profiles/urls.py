from django.urls import path
from .views import ProfileUploadView
urlpatterns=[path("uploads/validate/", ProfileUploadView.as_view(), name="profile-upload")]
