import pytest
from conftest import UserFactory, VaultMembershipFactory
from apps.vaults.models import VaultAuditLog, VaultMembership


class TestVaultMemberList:
    def test_list_members(self, site_admin_client, vault, editor_user):
        r = site_admin_client.get(f"/api/v1/vaults/{vault.id}/members/")
        assert r.status_code == 200
        assert len(r.data) >= 1

    def test_add_member(self, site_admin_client, vault):
        user = UserFactory()
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/members/", {
            "user": user.pk, "role": "editor",
        }, format="json")
        assert r.status_code == 201
        assert r.data["role"] == "editor"

    def test_add_member_audit_log(self, site_admin_client, vault):
        user = UserFactory()
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/members/", {
            "user": user.pk, "role": "editor",
        }, format="json")
        assert VaultAuditLog.objects.filter(vault=vault, event="member_added").exists()


class TestVaultMemberDetail:
    def test_update_role(self, site_admin_client, vault, editor_user):
        membership = VaultMembership.objects.get(vault=vault, user=editor_user)
        r = site_admin_client.patch(
            f"/api/v1/vaults/{vault.id}/members/{membership.id}/",
            {"role": "admin"},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["role"] == "admin"

    def test_role_change_audit_log(self, site_admin_client, vault, editor_user):
        membership = VaultMembership.objects.get(vault=vault, user=editor_user)
        site_admin_client.patch(
            f"/api/v1/vaults/{vault.id}/members/{membership.id}/",
            {"role": "admin"},
            format="json",
        )
        assert VaultAuditLog.objects.filter(vault=vault, event="member_role_changed").exists()

    def test_remove_member(self, site_admin_client, vault, editor_user):
        membership = VaultMembership.objects.get(vault=vault, user=editor_user)
        r = site_admin_client.delete(
            f"/api/v1/vaults/{vault.id}/members/{membership.id}/"
        )
        assert r.status_code == 204

    def test_remove_member_audit_log(self, site_admin_client, vault, editor_user):
        membership = VaultMembership.objects.get(vault=vault, user=editor_user)
        site_admin_client.delete(
            f"/api/v1/vaults/{vault.id}/members/{membership.id}/"
        )
        assert VaultAuditLog.objects.filter(vault=vault, event="member_removed").exists()

    def test_cannot_remove_last_admin(self, site_admin_client, vault):
        # Add admin member, then try to remove them — they're the only admin membership
        user = UserFactory()
        m = VaultMembershipFactory(vault=vault, user=user, role="admin")
        # Remove other admins first (none should exist besides this one as membership)
        # The fixture vault has no memberships by default, so this user is only admin
        r = site_admin_client.delete(
            f"/api/v1/vaults/{vault.id}/members/{m.id}/"
        )
        assert r.status_code == 400

    def test_cannot_modify_site_admin_membership(self, site_admin_client, vault, site_admin_user):
        m = VaultMembershipFactory(vault=vault, user=site_admin_user, role="admin")
        r = site_admin_client.patch(
            f"/api/v1/vaults/{vault.id}/members/{m.id}/",
            {"role": "viewer"},
            format="json",
        )
        assert r.status_code == 400

    def test_locked_vault_blocks_member_changes(self, site_admin_client, vault, editor_user):
        site_admin_client.post(f"/api/v1/vaults/{vault.id}/lock/")
        user = UserFactory()
        r = site_admin_client.post(f"/api/v1/vaults/{vault.id}/members/", {
            "user": user.pk, "role": "editor",
        }, format="json")
        assert r.status_code == 403
