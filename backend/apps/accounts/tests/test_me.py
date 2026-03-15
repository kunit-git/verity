import pytest
from conftest import UserFactory
from rest_framework.test import APIClient


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestMeGet:
    def test_returns_profile(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.get("/api/v1/auth/me/")
        assert r.status_code == 200
        assert r.data["username"] == user.username
        assert r.data["email"] == user.email
        assert "vault_role" in r.data

    def test_unauthenticated(self, api_client, db):
        r = api_client.get("/api/v1/auth/me/")
        assert r.status_code == 401


class TestMePatch:
    def test_update_email(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.patch("/api/v1/auth/me/", {"email": "new@email.com"}, format="json")
        assert r.status_code == 200
        assert r.data["email"] == "new@email.com"

    def test_cannot_change_is_site_admin(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.patch("/api/v1/auth/me/", {"is_site_admin": True}, format="json")
        assert r.status_code == 200
        assert r.data["is_site_admin"] is False


class TestChangeOwnPassword:
    def test_valid_change(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.post("/api/v1/auth/me/password/", {
            "current_password": "testpass123",
            "new_password": "newpass12345",
        }, format="json")
        assert r.status_code == 204

    def test_wrong_current_password(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.post("/api/v1/auth/me/password/", {
            "current_password": "wrongpass",
            "new_password": "newpass12345",
        }, format="json")
        assert r.status_code == 400

    def test_short_new_password(self, db):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.post("/api/v1/auth/me/password/", {
            "current_password": "testpass123",
            "new_password": "short",
        }, format="json")
        assert r.status_code == 400

    def test_unauthenticated(self, api_client, db):
        r = api_client.post("/api/v1/auth/me/password/", {
            "current_password": "x", "new_password": "y",
        }, format="json")
        assert r.status_code == 401
