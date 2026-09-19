from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY == "unsafe-dev-key-change-me":  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")
if len(SECRET_KEY.encode("utf-8")) < 32:  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY must be at least 32 bytes long in production because it signs JWTs."
    )

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

# Supabase Storage is mandatory for retained production artifacts.
if not SUPABASE_STORAGE_ENABLED:  # noqa: F405
    raise ImproperlyConfigured("SUPABASE_STORAGE_ENABLED must be True in production.")

_required_storage = {
    "SUPABASE_S3_ENDPOINT": SUPABASE_S3_ENDPOINT,  # noqa: F405
    "SUPABASE_S3_REGION": SUPABASE_S3_REGION,  # noqa: F405
    "SUPABASE_S3_ACCESS_KEY_ID": SUPABASE_S3_ACCESS_KEY_ID,  # noqa: F405
    "SUPABASE_S3_SECRET_ACCESS_KEY": SUPABASE_S3_SECRET_ACCESS_KEY,  # noqa: F405
    "SUPABASE_STORAGE_BUCKET": SUPABASE_STORAGE_BUCKET,  # noqa: F405
}
for _name, _value in _required_storage.items():
    if not str(_value or "").strip():
        raise ImproperlyConfigured(f"{_name} must be set in production.")

# The production database must be PostgreSQL (Supabase).
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("Production DATABASE_URL must point to PostgreSQL/Supabase.")
DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
DATABASES["default"]["OPTIONS"].setdefault("sslmode", "require")  # noqa: F405
DATABASES["default"]["OPTIONS"].setdefault("connect_timeout", DATABASE_CONNECT_TIMEOUT)  # noqa: F405
DATABASES["default"]["OPTIONS"].setdefault("application_name", "smart-battery-api")  # noqa: F405


# If email security features are enabled in production, SMTP credentials are mandatory.
if ACCOUNT_EMAIL_ENABLED:  # noqa: F405
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:  # noqa: F405
        raise ImproperlyConfigured(
            "EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set when ACCOUNT_EMAIL_ENABLED=True."
        )
    if not FRONTEND_URL.startswith("https://"):  # noqa: F405
        raise ImproperlyConfigured("FRONTEND_URL must use HTTPS in production when account email security is enabled.")
