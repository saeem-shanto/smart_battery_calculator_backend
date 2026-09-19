from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from apps.common.auth import AdminTokenObtainPairView, AdminTokenRefreshView
from apps.common.views import health, readiness, root

urlpatterns = [
    path("", root, name="root"),
    path("django-admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
    path("api/v1/ready/", readiness, name="readiness"),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/tariffs/", include("apps.tariffs.urls")),
    path("api/v1/profiles/", include("apps.profiles.urls")),
    path("api/v1/calculations/", include("apps.calculations.urls")),
    path("api/v1/feedback/", include("apps.feedback.urls")),
    path("api/v1/admin/auth/token/", AdminTokenObtainPairView.as_view(), name="admin-token"),
    path("api/v1/admin/auth/token/refresh/", AdminTokenRefreshView.as_view(), name="admin-token-refresh"),
    path("api/v1/admin/", include("apps.dashboard.urls")),
    # Keep the diagnostics routes registered in every environment. The views
    # themselves return 404 when OCTAVE_DIAGNOSTICS_ENABLED=False. This keeps
    # production diagnostics hidden while allowing override_settings() to
    # enable/disable the feature reliably in tests without reloading URLconf.
    path("api/v1/octave/", include("apps.octave.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
