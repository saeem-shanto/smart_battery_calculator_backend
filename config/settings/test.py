"""Isolated settings for the Django unit/integration-style test suite.

`python manage.py test` selects this module automatically through manage.py.
It intentionally avoids the developer's Supabase database and Storage bucket.
Set DJANGO_SETTINGS_MODULE explicitly if you intentionally want external
infrastructure integration tests.
"""

from .development import *  # noqa: F401,F403


# A deterministic, sufficiently long key prevents PyJWT's short-HMAC warning
# and is safe because this settings module is test-only.
SECRET_KEY = "smart-battery-test-secret-key-2026-do-not-use-in-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SUPABASE_STORAGE_ENABLED = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# WhiteNoise production static-file discovery is unnecessary in unit tests and
# otherwise warns when collectstatic has not been run.
MIDDLEWARE = [
    item
    for item in MIDDLEWARE  # noqa: F405
    if item != "whitenoise.middleware.WhiteNoiseMiddleware"
]

# Routes are always registered; the view-level guard is what tests toggle.
OCTAVE_DIAGNOSTICS_ENABLED = True

# The test suite mocks expensive execution paths and uses compact sample data.
REQUIRE_FULL_YEAR_PROFILE = False

# Speed up account/authentication tests without changing production hashing.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]