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


class VaultNotLocked(BasePermission):
    """Allows reads on any vault; blocks writes when the active vault is locked."""

    message = "This vault is locked. No modifications are allowed."

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        vault = getattr(request.user, "active_vault", None)
        if vault is None:
            return True  # other permissions will catch this
        return not vault.is_locked


class IsVaultAdminForVault(BasePermission):
    """Admin within a specific vault identified by URL pk (or site admin)."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_site_admin:
            return True
        vault_id = view.kwargs.get("pk")
        if vault_id is None:
            return False
        return VaultMembership.objects.filter(
            vault_id=vault_id, user=request.user, role="admin"
        ).exists()
