import pytest
from django.contrib.auth import get_user_model
from apps.accounts.models import SiteSettings

User = get_user_model()
URL = "/api/v1/auth/register/"


class TestRegistration:
    def test_valid_registration_returns_202(self, api_client):
        r = api_client.post(URL, {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        }, format="json")
        assert r.status_code == 202

    def test_registration_creates_locked_account(self, api_client):
        api_client.post(URL, {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        }, format="json")
        user = User.objects.get(username="newuser")
        assert user.account_status == "locked"
        assert user.is_active is False

    def test_registered_account_cannot_login(self, api_client):
        api_client.post(URL, {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        }, format="json")
        r = api_client.post("/api/v1/auth/login/", {
            "username": "newuser", "password": "securepass123",
        }, format="json")
        assert r.status_code == 401

    def test_duplicate_username(self, api_client):
        api_client.post(URL, {
            "username": "dupeuser", "email": "a@a.com", "password": "securepass123",
        }, format="json")
        r = api_client.post(URL, {
            "username": "dupeuser", "email": "b@b.com", "password": "securepass123",
        }, format="json")
        assert r.status_code == 400

    def test_short_password(self, api_client):
        r = api_client.post(URL, {
            "username": "shortpw", "email": "s@s.com", "password": "short",
        }, format="json")
        assert r.status_code == 400

    def test_missing_username(self, api_client):
        r = api_client.post(URL, {
            "email": "no@user.com", "password": "securepass123",
        }, format="json")
        assert r.status_code == 400

    def test_missing_password(self, api_client):
        r = api_client.post(URL, {
            "username": "nopw", "email": "nopw@test.com",
        }, format="json")
        assert r.status_code == 400

    def test_registration_disabled(self, api_client, site_settings):
        site_settings.registration_enabled = False
        site_settings.save()
        r = api_client.post(URL, {
            "username": "blocked", "email": "blocked@test.com", "password": "securepass123",
        }, format="json")
        assert r.status_code == 403
