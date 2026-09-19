from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY == "unsafe-dev-key-change-me":  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

if not env("DATABASE_URL", default="").strip():  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")

render_hostname = env("RENDER_EXTERNAL_HOSTNAME", default="").strip()  # noqa: F405
if render_hostname and render_hostname not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS.append(render_hostname)  # noqa: F405

if "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Wildcard ALLOWED_HOSTS is not permitted in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False
