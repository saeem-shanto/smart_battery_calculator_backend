from .base import *  # noqa: F401,F403

DEBUG = env.bool("DEBUG", default=True)  # noqa: F405
OCTAVE_DIAGNOSTICS_ENABLED = env.bool("OCTAVE_DIAGNOSTICS_ENABLED", default=True)  # noqa: F405
REQUIRE_FULL_YEAR_PROFILE = env.bool("REQUIRE_FULL_YEAR_PROFILE", default=False)  # noqa: F405

# Local development must not depend on a collectstatic manifest.
# The production settings keep WhiteNoise's hashed manifest storage.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")  # noqa: F405
ACCOUNT_EMAIL_ENABLED = env.bool("ACCOUNT_EMAIL_ENABLED", default=True)  # noqa: F405
