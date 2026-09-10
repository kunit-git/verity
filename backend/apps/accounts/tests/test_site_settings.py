import pytest
from rest_framework.test import APIClient
from conftest import UserFactory


URL = "/api/v1/auth/settings/"


class TestSiteSettingsGet:
    def test_public_settings_hide_provider_configuration(self, api_client, site_settings):
        site_settings.ai_api_url = "https://internal.example.com/api"
        site_settings.ai_api_key = "test-only-key"
        site_settings.save()
        response = api_client.get(URL)
        assert set(response.data) == {"registration_enabled", "mailbox_limit", "ai_enabled"}

    def test_admin_sees_configuration_but_not_key(self, site_admin_client, site_settings):
        site_settings.ai_api_key = "test-only-key"
        site_settings.save()
        response = site_admin_client.get(URL)
        assert "ai_api_url" in response.data
        assert response.data["ai_api_key_set"] is True
        assert "ai_api_key" not in response.data

    def test_anonymous_can_read(self, api_client, site_settings):
        r = api_client.get(URL)
        assert r.status_code == 200
        assert "registration_enabled" in r.data
        assert "mailbox_limit" in r.data

    def test_returns_defaults(self, api_client, site_settings):
        r = api_client.get(URL)
        assert r.data["registration_enabled"] is True
        assert r.data["mailbox_limit"] == 0


class TestSiteSettingsPatch:
    def test_site_admin_can_update(self, site_admin_client, site_settings):
        r = site_admin_client.patch(URL, {"registration_enabled": False}, format="json")
        assert r.status_code == 200
        assert r.data["registration_enabled"] is False

    def test_site_admin_can_update_mailbox_limit(self, site_admin_client, site_settings):
        r = site_admin_client.patch(URL, {"mailbox_limit": 10}, format="json")
        assert r.status_code == 200
        assert r.data["mailbox_limit"] == 10

    def test_non_admin_cannot_update(self, db, site_settings):
        user = UserFactory()
        client = APIClient()
        client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
        r = client.patch(URL, {"registration_enabled": False}, format="json")
        assert r.status_code in (401, 403)

    def test_unauthenticated_cannot_update(self, api_client, site_settings):
        r = api_client.patch(URL, {"registration_enabled": False}, format="json")
        assert r.status_code in (401, 403)
