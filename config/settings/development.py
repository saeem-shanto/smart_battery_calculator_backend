from .base import *  # noqa: F401,F403

DEBUG = env.bool("DEBUG", default=True)  # noqa: F405
OCTAVE_DIAGNOSTICS_ENABLED = env.bool("OCTAVE_DIAGNOSTICS_ENABLED", default=True)  # noqa: F405
REQUIRE_FULL_YEAR_PROFILE = env.bool("REQUIRE_FULL_YEAR_PROFILE", default=False)  # noqa: F405

WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
