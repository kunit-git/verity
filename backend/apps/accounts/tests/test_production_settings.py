import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("overrides", [
    {"SECRET_KEY": "short"},
    {"SECRET_KEY": "django-insecure-" + "x" * 60},
    {"ALLOWED_HOSTS": "*"},
    {"ALLOWED_HOSTS": ""},
])
def test_production_rejects_unsafe_configuration(overrides):
    env = {
        **os.environ,
        "SECRET_KEY": "production-config-test-only-" + "x" * 60,
        "ALLOWED_HOSTS": "verity.example.com",
        "DB_PASSWORD": "test-only",
        **overrides,
    }
    result = subprocess.run(
        [sys.executable, "-c", "import verity.settings.production"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr


def test_production_defaults_to_https_and_requires_proxy_opt_in():
    env = {
        **os.environ,
        "SECRET_KEY": "production-config-test-only-" + "x" * 60,
        "ALLOWED_HOSTS": "verity.example.com",
        "DB_PASSWORD": "test-only",
        "TRUST_PROXY_HEADERS": "False",
    }
    result = subprocess.run(
        [sys.executable, "-c", """
from verity.settings import production as settings
assert settings.SECURE_SSL_REDIRECT
assert settings.SESSION_COOKIE_SECURE
assert settings.CSRF_COOKIE_SECURE
assert settings.SECURE_HSTS_SECONDS > 0
assert not hasattr(settings, 'SECURE_PROXY_SSL_HEADER')
"""], env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
