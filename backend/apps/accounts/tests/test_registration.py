import pytest
from apps.accounts.models import SiteSettings


URL = "/api/v1/auth/register/"


class TestRegistration:
    def test_valid_registration(self, api_client):
        r = api_client.post(URL, {
            "username": "newuser",
            "email": "new@example.com",
            "password": "securepass123",
        }, format="json")
        assert r.status_code == 201
        assert r.data["username"] == "newuser"
        assert r.data["email"] == "new@example.com"
        assert "id" in r.data
        assert "password" not in r.data

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
