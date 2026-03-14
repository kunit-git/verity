from rest_framework.permissions import BasePermission


class IsSiteAdmin(BasePermission):
    """Site-level admin (vault CRUD, user management)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_site_admin


class IsEditorOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.get_vault_role() in (
            "editor",
            "admin",
        )


class IsViewerOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.get_vault_role() is not None


class ReadOnlyOrEditor(BasePermission):
    """Viewers get read-only; editors and admins get full access."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.get_vault_role() in ("editor", "admin")
