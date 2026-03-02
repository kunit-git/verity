from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"


class IsEditorOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("editor", "admin")


class IsViewerOrAbove(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (
            "viewer",
            "editor",
            "admin",
        )


class ReadOnlyOrEditor(BasePermission):
    """Viewers get read-only; editors and admins get full access."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role in ("editor", "admin")
