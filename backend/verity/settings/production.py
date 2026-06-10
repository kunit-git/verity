from .base import *  # noqa: F401, F403
from pathlib import Path

from decouple import config

DEBUG = False
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

# Never fall back to the insecure development defaults in production.
# decouple raises if these are unset, so a misconfigured deploy fails loudly
# instead of silently running on a public, source-committed key/password.
SECRET_KEY = config("SECRET_KEY")
DATABASES["default"]["PASSWORD"] = config("DB_PASSWORD")  # noqa: F405

STATIC_ROOT = Path(__file__).resolve().parent.parent.parent / "staticfiles"
