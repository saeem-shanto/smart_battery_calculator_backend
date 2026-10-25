from .base import *  # noqa: F401,F403

# =============================================================================
# DEVELOPMENT SETTINGS
# =============================================================================

DEBUG = env.bool("DEBUG", default=True)  # noqa: F405

# =============================================================================
# LOCAL HOSTS / CORS / CSRF
# =============================================================================

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Local development uses HTTP.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# =============================================================================
# CALCULATION ENGINE
# =============================================================================

OCTAVE_DIAGNOSTICS_ENABLED = env.bool(
    "OCTAVE_DIAGNOSTICS_ENABLED",
    default=True,
)  # noqa: F405

REQUIRE_FULL_YEAR_PROFILE = env.bool(
    "REQUIRE_FULL_YEAR_PROFILE",
    default=False,
)  # noqa: F405

# =============================================================================
# STATIC FILES
# =============================================================================

# Development does not require a collectstatic manifest.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

# =============================================================================
# EMAIL
# =============================================================================

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)  # noqa: F405

ACCOUNT_EMAIL_ENABLED = env.bool(
    "ACCOUNT_EMAIL_ENABLED",
    default=True,
)  # noqa: F405
