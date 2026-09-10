import pytest

from conftest import UserFactory, VaultFactory, VaultMembershipFactory
from apps.vaults.models import VaultMembership


@pytest.mark.parametrize("operation", ["list", "add", "retrieve", "update", "delete", "audit"])
def test_admin_of_one_vault_cannot_manage_another(editor_client, editor_user, vault, operation):
    VaultMembership.objects.filter(vault=vault, user=editor_user).update(role="admin")
    foreign_vault = VaultFactory()
    member = VaultMembershipFactory(vault=foreign_vault)
    user = UserFactory()
    base = f"/api/v1/vaults/{foreign_vault.pk}"
    detail = f"{base}/members/{member.pk}/"
    if operation == "list":
        response = editor_client.get(f"{base}/members/")
    elif operation == "add":
        response = editor_client.post(f"{base}/members/", {"user": user.pk, "role": "admin"}, format="json")
    elif operation == "retrieve":
        response = editor_client.get(detail)
    elif operation == "update":
        response = editor_client.patch(detail, {"role": "admin"}, format="json")
    elif operation == "delete":
        response = editor_client.delete(detail)
    else:
        response = editor_client.get(f"{base}/audit-log/")
    assert response.status_code == 403
    member.refresh_from_db()
    assert not member.is_deleted
    assert member.role == "editor"
    assert not VaultMembership.objects.filter(vault=foreign_vault, user=user).exists()


@pytest.mark.parametrize("endpoint", ["members", "audit-log"])
def test_target_vault_admin_can_read_without_switching_active_vault(editor_client, editor_user, endpoint):
    target = VaultFactory()
    VaultMembershipFactory(vault=target, user=editor_user, role="admin")
    response = editor_client.get(f"/api/v1/vaults/{target.pk}/{endpoint}/")
    assert response.status_code == 200
