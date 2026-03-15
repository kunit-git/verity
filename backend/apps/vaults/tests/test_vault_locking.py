import pytest
from conftest import VaultFactory, VaultMembershipFactory, UserFactory, ItemTypeFactory, ItemFactory
from rest_framework.test import APIClient
from apps.vaults.models import VaultAuditLog


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestVaultLock:
    def test_lock_success(self, site_admin_client, vault):
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        assert r.status_code == 200
        assert "locked" in r.data["detail"].lower()

    def test_already_locked(self, site_admin_client, vault):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        assert r.status_code == 400

    def test_audit_log_created(self, site_admin_client, vault):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        assert VaultAuditLog.objects.filter(vault=vault, event="vault_locked").exists()

    def test_vault_admin_can_lock(self, db, vault):
        user = UserFactory()
        VaultMembershipFactory(vault=vault, user=user, role="admin")
        client = _auth(APIClient(), user)
        r = client.post(f"/api/v1/vaults/{vault.id}/lock/")
        assert r.status_code == 200

    def test_non_admin_forbidden(self, db, vault):
        user = UserFactory()
        VaultMembershipFactory(vault=vault, user=user, role="editor")
        client = _auth(APIClient(), user)
        r = client.post(f"/api/v1/vaults/{vault.id}/lock/")
        assert r.status_code == 403


class TestVaultUnlock:
    def test_unlock_success(self, site_admin_client, vault):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/unlock/")
        assert r.status_code == 200

    def test_not_locked(self, site_admin_client, vault):
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/unlock/")
        assert r.status_code == 400

    def test_audit_log_created(self, site_admin_client, vault):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/unlock/")
        assert VaultAuditLog.objects.filter(vault=vault, event="vault_unlocked").exists()


class TestLockedVaultBlocksWrites:
    def test_locked_vault_blocks_item_creation(self, site_admin_client, vault, site_admin_user):
        item_type = ItemTypeFactory(vault=vault)
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        # Refresh vault state on user
        site_admin_user.refresh_from_db()
        r = site_admin_client.post("/api/v1/items/", {
            "title": "Blocked", "item_type": str(item_type.id),
        }, format="json")
        assert r.status_code == 403

    def test_locked_vault_allows_reads(self, site_admin_client, vault, site_admin_user):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        site_admin_user.refresh_from_db()
        r = site_admin_client.get("/api/v1/items/")
        assert r.status_code == 200
