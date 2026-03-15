from .base import *  # noqa

DEBUG = False
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK["PAGE_SIZE"] = 100  # noqa: F405
