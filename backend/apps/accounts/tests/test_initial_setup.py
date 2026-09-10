import pytest
from django.contrib.auth import get_user_model
from conftest import UserFactory

User = get_user_model()

SETUP_URL = "/api/v1/auth/setup/"


@pytest.fixture(autouse=True)
def clear_setup_throttle():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


class TestSetupStatus:
    def test_returns_setup_required_when_no_admins(self, api_client, db):
        r = api_client.get(SETUP_URL)
        assert r.status_code == 200
        assert r.data["setup_required"] is True

    def test_returns_not_required_when_admin_exists(self, api_client, db):
        UserFactory(is_site_admin=True)
        r = api_client.get(SETUP_URL)
        assert r.status_code == 200
        assert r.data["setup_required"] is False

    def test_non_admin_user_does_not_satisfy_setup(self, api_client, db):
        UserFactory(is_site_admin=False)
        r = api_client.get(SETUP_URL)
        assert r.status_code == 200
        assert r.data["setup_required"] is True


class TestSetupCreate:
    @pytest.mark.parametrize("payload", [
        {"username": None, "password": "securepass1"},
        {"username": [], "password": "securepass1"},
        {"username": "invalid username", "password": "securepass1"},
        {"username": "a" * 151, "password": "securepass1"},
        {"username": "admin", "password": None},
        {"username": "admin", "password": []},
    ])
    def test_malformed_input_returns_400(self, api_client, db, payload):
        response = api_client.post(SETUP_URL, payload, format="json")
        assert response.status_code == 400
        assert not User.objects.filter(is_site_admin=True).exists()

    def test_creates_admin_when_none_exist(self, api_client, db):
        r = api_client.post(
            SETUP_URL,
            {"username": "newadmin", "password": "securepass1"},
            format="json",
        )
        assert r.status_code == 201
        user = User.objects.get(username="newadmin")
        assert user.is_site_admin is True
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_rejects_when_admin_already_exists(self, api_client, db):
        UserFactory(is_site_admin=True)
        r = api_client.post(
            SETUP_URL,
            {"username": "anotheradmin", "password": "securepass1"},
            format="json",
        )
        assert r.status_code == 409

    def test_rejects_short_password(self, api_client, db):
        r = api_client.post(
            SETUP_URL,
            {"username": "admin", "password": "short"},
            format="json",
        )
        assert r.status_code == 400
        assert "password" in r.data

    def test_rejects_missing_username(self, api_client, db):
        r = api_client.post(
            SETUP_URL,
            {"username": "", "password": "securepass1"},
            format="json",
        )
        assert r.status_code == 400
        assert "username" in r.data

    def test_rejects_duplicate_username(self, api_client, db):
        UserFactory(username="existinguser", is_site_admin=False)
        r = api_client.post(
            SETUP_URL,
            {"username": "existinguser", "password": "securepass1"},
            format="json",
        )
        assert r.status_code == 400
        assert "username" in r.data

    def test_created_admin_can_login(self, api_client, db):
        api_client.post(
            SETUP_URL,
            {"username": "newadmin", "password": "securepass1"},
            format="json",
        )
        r = api_client.post(
            "/api/v1/auth/login/",
            {"username": "newadmin", "password": "securepass1"},
            format="json",
        )
        assert r.status_code == 200
        assert "access" in r.data


@pytest.mark.django_db(transaction=True)
def test_concurrent_setup_creates_only_one_admin():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    from rest_framework.test import APIClient
    from apps.accounts.models import SiteSettings

    SiteSettings.get()
    barrier = Barrier(2)

    def create_admin(username):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return APIClient().post(
                SETUP_URL,
                {"username": username, "password": "securepass1"},
                format="json",
            ).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(create_admin, ["firstadmin", "secondadmin"]))
    assert sorted(statuses) == [201, 409]
    assert User.objects.filter(is_site_admin=True).count() == 1
