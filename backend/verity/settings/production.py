from .base import *  # noqa: F401, F403
from pathlib import Path

from decouple import config
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

# Never fall back to the insecure development defaults in production.
# decouple raises if these are unset, so a misconfigured deploy fails loudly
# instead of silently running on a public, source-committed key/password.
SECRET_KEY = config("SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Production SECRET_KEY must be a unique, strong key of at least 50 characters.")
DATABASES["default"]["PASSWORD"] = config("DB_PASSWORD")  # noqa: F405

if not ALLOWED_HOSTS or any(not host or "*" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Production ALLOWED_HOSTS must list explicit hostnames.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
# Enable only behind a trusted proxy that overwrites this header and blocks
# direct access to Gunicorn.
if config("TRUST_PROXY_HEADERS", default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

STATIC_ROOT = Path(__file__).resolve().parent.parent.parent / "staticfiles"
