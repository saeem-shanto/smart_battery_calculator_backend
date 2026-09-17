from .base import *  # noqa: F401,F403

DEBUG = env.bool("DEBUG", default=True)  # noqa: F405

# In development, let WhiteNoise discover source static files directly as well.
# This makes local behaviour closer to production while still allowing runserver.
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
