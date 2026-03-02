from .base import *  # noqa: F401, F403
from pathlib import Path

from decouple import config

DEBUG = False
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=lambda v: [s.strip() for s in v.split(",")],
)

STATIC_ROOT = Path(__file__).resolve().parent.parent.parent / "staticfiles"
