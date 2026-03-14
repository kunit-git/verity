from rest_framework.permissions import BasePermission

from .models import VaultMembership


class HasVaultAccess(BasePermission):
    """Checks user has an active vault selected and is a member (or site admin)."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if not request.user.active_vault_id:
            return False
        if request.user.is_site_admin:
            return True
        return VaultMembership.objects.filter(
            vault_id=request.user.active_vault_id,
            user=request.user,
        ).exists()


class IsVaultAdmin(BasePermission):
    """Admin within the active vault (or site admin)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.get_vault_role() == "admin"
