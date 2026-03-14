from rest_framework.exceptions import PermissionDenied


class VaultScopedMixin:
    """View mixin that reads the active vault from the request user."""

    @property
    def current_vault(self):
        vault = getattr(self.request.user, "active_vault", None)
        if vault is None:
            raise PermissionDenied("No active vault selected.")
        return vault

    @property
    def current_vault_id(self):
        vault_id = getattr(self.request.user, "active_vault_id", None)
        if vault_id is None:
            raise PermissionDenied("No active vault selected.")
        return vault_id
