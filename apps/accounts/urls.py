from django.urls import path

from .views import (
    AvatarDownloadView,
    LogoutView,
    MeView,
    MyCalculationsView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    TwoFactorDisableView,
    TwoFactorEnableStartView,
    TwoFactorEnableVerifyView,
    TwoFactorResendView,
    TwoFactorStatusView,
    TwoFactorVerifyView,
    UserTokenObtainPairView,
    UserTokenRefreshView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="account-register"),
    path("auth/token/", UserTokenObtainPairView.as_view(), name="account-token"),
    path("auth/token/refresh/", UserTokenRefreshView.as_view(), name="account-token-refresh"),
    path("auth/2fa/verify/", TwoFactorVerifyView.as_view(), name="account-2fa-verify"),
    path("auth/2fa/resend/", TwoFactorResendView.as_view(), name="account-2fa-resend"),
    path("auth/logout/", LogoutView.as_view(), name="account-logout"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="account-password-reset"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="account-password-reset-confirm"),
    path("me/", MeView.as_view(), name="account-me"),
    path("me/avatar/", AvatarDownloadView.as_view(), name="account-avatar"),
    path("me/password/", PasswordChangeView.as_view(), name="account-password"),
    path("me/two-factor/", TwoFactorStatusView.as_view(), name="account-two-factor-status"),
    path("me/two-factor/enable/", TwoFactorEnableStartView.as_view(), name="account-two-factor-enable"),
    path("me/two-factor/enable/verify/", TwoFactorEnableVerifyView.as_view(), name="account-two-factor-enable-verify"),
    path("me/two-factor/disable/", TwoFactorDisableView.as_view(), name="account-two-factor-disable"),
    path("me/calculations/", MyCalculationsView.as_view(), name="account-calculations"),
]
