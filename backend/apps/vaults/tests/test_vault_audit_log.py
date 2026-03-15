import pytest


class TestVaultAuditLog:
    def test_returns_entries(self, site_admin_client, vault):
        # Lock to generate an audit event
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        r = site_admin_client.get(f"/api/v1/vaults/{vault.id}/audit-log/")
        assert r.status_code == 200
        assert r.data["count"] >= 1

    def test_non_admin_forbidden(self, viewer_client, vault):
        r = viewer_client.get(f"/api/v1/vaults/{vault.id}/audit-log/")
        assert r.status_code == 403
