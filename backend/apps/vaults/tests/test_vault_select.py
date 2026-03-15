import pytest
import uuid
from conftest import UserFactory, VaultFactory, VaultMembershipFactory
from rest_framework.test import APIClient


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestSelectVault:
    def test_site_admin_can_select_any(self, site_admin_client, db, site_admin_user):
        vault = VaultFactory(created_by=site_admin_user)
        r = site_admin_client.post("/api/v1/vaults/select/", {
            "vault_id": str(vault.id),
        }, format="json")
        assert r.status_code == 200
        assert r.data["vault_name"] == vault.name

    def test_member_can_select(self, db, vault):
        user = UserFactory()
        VaultMembershipFactory(vault=vault, user=user, role="viewer")
        client = _auth(APIClient(), user)
        r = client.post("/api/v1/vaults/select/", {
            "vault_id": str(vault.id),
        }, format="json")
        assert r.status_code == 200

    def test_non_member_forbidden(self, db, vault):
        user = UserFactory()
        client = _auth(APIClient(), user)
        r = client.post("/api/v1/vaults/select/", {
            "vault_id": str(vault.id),
        }, format="json")
        assert r.status_code == 403

    def test_nonexistent_vault(self, site_admin_client):
        r = site_admin_client.post("/api/v1/vaults/select/", {
            "vault_id": str(uuid.uuid4()),
        }, format="json")
        assert r.status_code == 404


class TestMyVaults:
    def test_member_sees_own_vaults(self, db):
        user = UserFactory()
        v1 = VaultFactory(created_by=UserFactory(is_site_admin=True))
        v2 = VaultFactory(created_by=UserFactory(is_site_admin=True))
        VaultMembershipFactory(vault=v1, user=user, role="viewer")
        client = _auth(APIClient(), user)
        r = client.get("/api/v1/vaults/my/")
        assert r.status_code == 200
        vault_ids = [v["id"] for v in r.data]
        assert str(v1.id) in vault_ids
        assert str(v2.id) not in vault_ids

    def test_site_admin_sees_all(self, site_admin_client, vault, db, site_admin_user):
        v2 = VaultFactory(created_by=site_admin_user)
        r = site_admin_client.get("/api/v1/vaults/my/")
        assert r.status_code == 200
        assert len(r.data) >= 2
