import pytest
from conftest import UserFactory, VaultFactory, VaultMembershipFactory
from rest_framework.test import APIClient


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestUserList:
    def test_site_admin_lists_users(self, site_admin_client, db):
        UserFactory()
        r = site_admin_client.get("/api/v1/auth/users/")
        assert r.status_code == 200
        assert len(r.data) >= 2  # site admin + created user

    def test_include_deleted(self, site_admin_client, db):
        user = UserFactory(account_status="deleted", is_active=False)
        r = site_admin_client.get("/api/v1/auth/users/?include_deleted=true")
        usernames = [u["username"] for u in r.data]
        assert user.username in usernames

    def test_excludes_deleted_by_default(self, site_admin_client, db):
        user = UserFactory(account_status="deleted", is_active=False)
        r = site_admin_client.get("/api/v1/auth/users/")
        usernames = [u["username"] for u in r.data]
        assert user.username not in usernames

    def test_vault_admin_can_list(self, db, vault):
        user = UserFactory()
        VaultMembershipFactory(vault=vault, user=user, role="admin")
        user.active_vault = vault
        user.save(update_fields=["active_vault"])
        client = _auth(APIClient(), user)
        r = client.get("/api/v1/auth/users/")
        assert r.status_code == 200

    def test_viewer_cannot_list(self, viewer_client):
        r = viewer_client.get("/api/v1/auth/users/")
        assert r.status_code == 403


class TestAdminCreateUser:
    def test_create_user(self, site_admin_client):
        r = site_admin_client.post("/api/v1/auth/users/create/", {
            "username": "created", "email": "c@c.com", "password": "securepass123",
        }, format="json")
        assert r.status_code == 201
        assert r.data["username"] == "created"

    def test_non_admin_cannot_create(self, editor_client):
        r = editor_client.post("/api/v1/auth/users/create/", {
            "username": "nope", "email": "n@n.com", "password": "securepass123",
        }, format="json")
        assert r.status_code == 403


class TestUserDetail:
    def test_site_admin_can_get(self, site_admin_client, regular_user):
        r = site_admin_client.get(f"/api/v1/auth/users/{regular_user.pk}/")
        assert r.status_code == 200
        assert r.data["username"] == regular_user.username

    def test_site_admin_can_patch(self, site_admin_client, regular_user):
        r = site_admin_client.patch(
            f"/api/v1/auth/users/{regular_user.pk}/",
            {"is_site_admin": True},
            format="json",
        )
        assert r.status_code == 200

    def test_non_admin_cannot_access(self, editor_client, regular_user):
        r = editor_client.get(f"/api/v1/auth/users/{regular_user.pk}/")
        assert r.status_code == 403


class TestAdminChangePassword:
    def test_valid(self, site_admin_client, regular_user):
        r = site_admin_client.post(
            f"/api/v1/auth/users/{regular_user.pk}/password/",
            {"new_password": "newpass12345"},
            format="json",
        )
        assert r.status_code == 204

    def test_deleted_user(self, site_admin_client, db):
        user = UserFactory(account_status="deleted")
        r = site_admin_client.post(
            f"/api/v1/auth/users/{user.pk}/password/",
            {"new_password": "newpass12345"},
            format="json",
        )
        assert r.status_code == 400

    def test_short_password(self, site_admin_client, regular_user):
        r = site_admin_client.post(
            f"/api/v1/auth/users/{regular_user.pk}/password/",
            {"new_password": "short"},
            format="json",
        )
        assert r.status_code == 400

    def test_non_admin(self, editor_client, regular_user):
        r = editor_client.post(
            f"/api/v1/auth/users/{regular_user.pk}/password/",
            {"new_password": "newpass12345"},
            format="json",
        )
        assert r.status_code == 403


class TestLockUser:
    def test_lock_success(self, site_admin_client, regular_user):
        r = site_admin_client.post(f"/api/v1/auth/users/{regular_user.pk}/lock/")
        assert r.status_code == 200
        assert r.data["account_status"] == "locked"

    def test_cannot_lock_self(self, site_admin_client, site_admin_user):
        r = site_admin_client.post(f"/api/v1/auth/users/{site_admin_user.pk}/lock/")
        assert r.status_code == 400

    def test_cannot_lock_deleted(self, site_admin_client, db):
        user = UserFactory(account_status="deleted")
        r = site_admin_client.post(f"/api/v1/auth/users/{user.pk}/lock/")
        assert r.status_code == 400

    def test_non_admin(self, editor_client, regular_user):
        r = editor_client.post(f"/api/v1/auth/users/{regular_user.pk}/lock/")
        assert r.status_code == 403


class TestUnlockUser:
    def test_unlock_success(self, site_admin_client, db):
        user = UserFactory(account_status="locked", is_active=False)
        r = site_admin_client.post(f"/api/v1/auth/users/{user.pk}/unlock/")
        assert r.status_code == 200
        assert r.data["account_status"] == "active"

    def test_not_locked(self, site_admin_client, regular_user):
        r = site_admin_client.post(f"/api/v1/auth/users/{regular_user.pk}/unlock/")
        assert r.status_code == 400


class TestDeleteUser:
    def test_delete_success(self, site_admin_client, regular_user):
        r = site_admin_client.post(f"/api/v1/auth/users/{regular_user.pk}/delete/")
        assert r.status_code == 200
        assert r.data["account_status"] == "deleted"

    def test_cannot_delete_self(self, site_admin_client, site_admin_user):
        r = site_admin_client.post(f"/api/v1/auth/users/{site_admin_user.pk}/delete/")
        assert r.status_code == 400

    def test_already_deleted(self, site_admin_client, db):
        user = UserFactory(account_status="deleted")
        r = site_admin_client.post(f"/api/v1/auth/users/{user.pk}/delete/")
        assert r.status_code == 400

    def test_non_admin(self, editor_client, regular_user):
        r = editor_client.post(f"/api/v1/auth/users/{regular_user.pk}/delete/")
        assert r.status_code == 403
