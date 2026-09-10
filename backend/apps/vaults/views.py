from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSiteAdmin
from .models import Vault, VaultAuditLog, VaultMembership
from .permissions import IsVaultAdminForVault
from .serializers import (
    VaultSerializer,
    VaultMembershipSerializer,
    VaultAuditLogSerializer,
    SelectVaultSerializer,
)

User = get_user_model()


def _log_audit(vault, event, actor, detail=None):
    VaultAuditLog.objects.create(
        vault=vault,
        event=event,
        actor=actor,
        detail=detail or {},
    )


class VaultListCreateView(generics.ListCreateAPIView):
    serializer_class = VaultSerializer
    permission_classes = [IsSiteAdmin]
    pagination_class = None

    def get_queryset(self):
        return Vault.objects.select_related("created_by", "locked_by").all()

    def perform_create(self, serializer):
        vault = serializer.save()
        _log_audit(vault, VaultAuditLog.Event.VAULT_CREATED, self.request.user)


class VaultDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VaultSerializer
    permission_classes = [IsSiteAdmin]

    def get_queryset(self):
        return Vault.objects.select_related("created_by", "locked_by").all()

    http_method_names = ["get", "patch", "delete", "head", "options"]


class VaultMemberListView(generics.ListCreateAPIView):
    serializer_class = VaultMembershipSerializer
    permission_classes = [IsVaultAdminForVault]
    pagination_class = None

    def get_queryset(self):
        return VaultMembership.objects.filter(
            vault_id=self.kwargs["vault_id"]
        ).select_related("user")

    def _check_vault_locked(self):
        vault = Vault.objects.filter(pk=self.kwargs["vault_id"]).values("is_locked").first()
        if vault and vault["is_locked"]:
            return Response(
                {"detail": "This vault is locked. No modifications are allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def create(self, request, *args, **kwargs):
        err = self._check_vault_locked()
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        membership = serializer.save(vault_id=self.kwargs["vault_id"])
        _log_audit(
            membership.vault,
            VaultAuditLog.Event.MEMBER_ADDED,
            self.request.user,
            {"user": membership.user.username, "role": membership.role},
        )


class VaultMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VaultMembershipSerializer
    permission_classes = [IsVaultAdminForVault]

    def get_queryset(self):
        return VaultMembership.objects.filter(
            vault_id=self.kwargs["vault_id"]
        ).select_related("user")

    def get_object(self):
        return generics.get_object_or_404(
            self.get_queryset(), pk=self.kwargs["membership_id"]
        )

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def _check_site_admin(self, membership):
        """Return an error response if the membership belongs to a site admin."""
        if membership.user.is_site_admin:
            return Response(
                {"detail": "Cannot modify a site admin's vault membership."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def _check_vault_locked(self):
        vault = Vault.objects.filter(pk=self.kwargs["vault_id"]).values("is_locked").first()
        if vault and vault["is_locked"]:
            return Response(
                {"detail": "This vault is locked. No modifications are allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def update(self, request, *args, **kwargs):
        err = self._check_vault_locked()
        if err:
            return err
        membership = self.get_object()
        err = self._check_site_admin(membership)
        if err:
            return err
        old_role = membership.role
        response = super().update(request, *args, **kwargs)
        membership.refresh_from_db()
        if membership.role != old_role:
            _log_audit(
                membership.vault,
                VaultAuditLog.Event.MEMBER_ROLE_CHANGED,
                request.user,
                {
                    "user": membership.user.username,
                    "old_role": old_role,
                    "new_role": membership.role,
                },
            )
        return response

    def partial_update(self, request, *args, **kwargs):
        # Checks and audit logging happen in update() which DRF calls from here.
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        err = self._check_vault_locked()
        if err:
            return err
        membership = self.get_object()
        err = self._check_site_admin(membership)
        if err:
            return err
        if membership.role == "admin":
            admin_count = VaultMembership.objects.filter(
                vault_id=self.kwargs["vault_id"], role="admin"
            ).count()
            if admin_count <= 1:
                return Response(
                    {"detail": "Cannot remove the last admin from a vault."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        username = membership.user.username
        vault = membership.vault
        response = super().destroy(request, *args, **kwargs)
        _log_audit(
            vault,
            VaultAuditLog.Event.MEMBER_REMOVED,
            request.user,
            {"user": username},
        )
        return response


class VaultLockView(APIView):
    permission_classes = [IsSiteAdmin | IsVaultAdminForVault]

    def post(self, request, pk):
        try:
            vault = Vault.objects.get(pk=pk)
        except Vault.DoesNotExist:
            return Response({"detail": "Vault not found."}, status=status.HTTP_404_NOT_FOUND)

        if vault.is_locked:
            return Response({"detail": "Vault is already locked."}, status=status.HTTP_400_BAD_REQUEST)

        vault.is_locked = True
        vault.locked_at = timezone.now()
        vault.locked_by = request.user
        vault.save(update_fields=["is_locked", "locked_at", "locked_by"])
        _log_audit(vault, VaultAuditLog.Event.VAULT_LOCKED, request.user)
        return Response({"detail": "Vault locked."})


class VaultUnlockView(APIView):
    permission_classes = [IsSiteAdmin | IsVaultAdminForVault]

    def post(self, request, pk):
        try:
            vault = Vault.objects.get(pk=pk)
        except Vault.DoesNotExist:
            return Response({"detail": "Vault not found."}, status=status.HTTP_404_NOT_FOUND)

        if not vault.is_locked:
            return Response({"detail": "Vault is not locked."}, status=status.HTTP_400_BAD_REQUEST)

        vault.is_locked = False
        vault.locked_at = None
        vault.locked_by = None
        vault.save(update_fields=["is_locked", "locked_at", "locked_by"])
        _log_audit(vault, VaultAuditLog.Event.VAULT_UNLOCKED, request.user)
        return Response({"detail": "Vault unlocked."})


class VaultAuditLogView(generics.ListAPIView):
    serializer_class = VaultAuditLogSerializer
    permission_classes = [IsVaultAdminForVault]

    def get_queryset(self):
        return VaultAuditLog.objects.filter(
            vault_id=self.kwargs["vault_id"]
        ).select_related("actor")


class SelectVaultView(APIView):
    def post(self, request):
        serializer = SelectVaultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vault_id = serializer.validated_data["vault_id"]

        try:
            vault = Vault.objects.get(pk=vault_id)
        except Vault.DoesNotExist:
            return Response(
                {"detail": "Vault not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check access: site admin can access any vault, others need membership
        if not request.user.is_site_admin:
            if not VaultMembership.objects.filter(
                vault=vault, user=request.user
            ).exists():
                return Response(
                    {"detail": "You are not a member of this vault."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        request.user.active_vault = vault
        request.user.save(update_fields=["active_vault"])
        return Response({"detail": "Vault selected.", "vault_id": str(vault.id), "vault_name": vault.name})


class MyVaultsView(generics.ListAPIView):
    serializer_class = VaultSerializer
    pagination_class = None

    def get_queryset(self):
        if self.request.user.is_site_admin:
            return Vault.objects.select_related("created_by", "locked_by").all()
        vault_ids = VaultMembership.objects.filter(
            user=self.request.user
        ).values_list("vault_id", flat=True)
        return Vault.objects.filter(id__in=vault_ids).select_related("created_by", "locked_by")
