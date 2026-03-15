import pytest
from conftest import UserFactory


class TestLogin:
    def test_valid_login(self, api_client, db):
        user = UserFactory()
        r = api_client.post("/api/v1/auth/login/", {
            "username": user.username, "password": "testpass123",
        }, format="json")
        assert r.status_code == 200
        assert "access" in r.data
        assert "refresh" in r.data

    def test_wrong_password(self, api_client, db):
        user = UserFactory()
        r = api_client.post("/api/v1/auth/login/", {
            "username": user.username, "password": "wrongpass",
        }, format="json")
        assert r.status_code == 401

    def test_nonexistent_user(self, api_client, db):
        r = api_client.post("/api/v1/auth/login/", {
            "username": "ghost", "password": "testpass123",
        }, format="json")
        assert r.status_code == 401

    def test_locked_account(self, api_client, db):
        user = UserFactory(account_status="locked", is_active=False)
        r = api_client.post("/api/v1/auth/login/", {
            "username": user.username, "password": "testpass123",
        }, format="json")
        assert r.status_code == 401


class TestTokenRefresh:
    def test_valid_refresh(self, api_client, db):
        user = UserFactory()
        login = api_client.post("/api/v1/auth/login/", {
            "username": user.username, "password": "testpass123",
        }, format="json")
        r = api_client.post("/api/v1/auth/refresh/", {
            "refresh": login.data["refresh"],
        }, format="json")
        assert r.status_code == 200
        assert "access" in r.data

    def test_invalid_refresh_token(self, api_client, db):
        r = api_client.post("/api/v1/auth/refresh/", {
            "refresh": "invalid-token",
        }, format="json")
        assert r.status_code == 401
