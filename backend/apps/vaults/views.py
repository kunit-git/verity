from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSiteAdmin
from .models import Vault, VaultMembership
from .permissions import IsVaultAdmin
from .serializers import VaultSerializer, VaultMembershipSerializer, SelectVaultSerializer

User = get_user_model()


class VaultListCreateView(generics.ListCreateAPIView):
    serializer_class = VaultSerializer
    permission_classes = [IsSiteAdmin]
    pagination_class = None

    def get_queryset(self):
        return Vault.objects.select_related("created_by").all()


class VaultDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VaultSerializer
    permission_classes = [IsSiteAdmin]

    def get_queryset(self):
        return Vault.objects.select_related("created_by").all()

    http_method_names = ["get", "patch", "delete", "head", "options"]


class VaultMemberListView(generics.ListCreateAPIView):
    serializer_class = VaultMembershipSerializer
    permission_classes = [IsSiteAdmin | IsVaultAdmin]
    pagination_class = None

    def get_queryset(self):
        return VaultMembership.objects.filter(
            vault_id=self.kwargs["vault_id"]
        ).select_related("user")

    def perform_create(self, serializer):
        serializer.save(vault_id=self.kwargs["vault_id"])


class VaultMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VaultMembershipSerializer
    permission_classes = [IsSiteAdmin | IsVaultAdmin]

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

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        err = self._check_site_admin(membership)
        if err:
            return err
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        err = self._check_site_admin(membership)
        if err:
            return err
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
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
        return super().destroy(request, *args, **kwargs)


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
            return Vault.objects.select_related("created_by").all()
        vault_ids = VaultMembership.objects.filter(
            user=self.request.user
        ).values_list("vault_id", flat=True)
        return Vault.objects.filter(id__in=vault_ids).select_related("created_by")
