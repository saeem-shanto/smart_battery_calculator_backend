from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

# Render provides this automatically. Adding it here prevents DisallowedHost/400
# without hard-coding one deployment hostname.
render_hostname = env("RENDER_EXTERNAL_HOSTNAME", default="").strip()  # noqa: F405
if render_hostname and render_hostname not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS.append(render_hostname)  # noqa: F405

if SECRET_KEY == "unsafe-dev-key-change-me":  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

# Reverse proxies (Nginx, Render, Hostinger proxy, etc.) commonly terminate TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)  # noqa: F405
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False

WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False
