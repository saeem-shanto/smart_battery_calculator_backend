from django.urls import path
from .views import (
    AvatarDownloadView,
    LogoutView,
    MeView,
    MyCalculationsView,
    PasswordChangeView,
    RegisterView,
    UserTokenObtainPairView,
    UserTokenRefreshView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="account-register"),
    path("auth/token/", UserTokenObtainPairView.as_view(), name="account-token"),
    path("auth/token/refresh/", UserTokenRefreshView.as_view(), name="account-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="account-logout"),
    path("me/", MeView.as_view(), name="account-me"),
    path("me/avatar/", AvatarDownloadView.as_view(), name="account-avatar"),
    path("me/password/", PasswordChangeView.as_view(), name="account-password"),
    path("me/calculations/", MyCalculationsView.as_view(), name="account-calculations"),
]
