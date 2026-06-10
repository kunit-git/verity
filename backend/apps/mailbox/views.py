from django.core.exceptions import ValidationError

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import SiteSettings
from apps.items.models import Item
from apps.vaults.mixins import VaultScopedMixin
from apps.vaults.permissions import HasVaultAccess

from .document_generator import generate_markdown
from .models import MailboxArtifact
from .serializers import MailboxArtifactSerializer, MailboxArtifactDetailSerializer


class MailboxViewSet(VaultScopedMixin, viewsets.ModelViewSet):
    permission_classes = [HasVaultAccess]
    http_method_names = ["get", "delete", "post"]

    def get_queryset(self):
        return MailboxArtifact.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MailboxArtifactDetailSerializer
        return MailboxArtifactSerializer

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        item_id = request.data.get("item_id")
        if not item_id:
            return Response(
                {"detail": "item_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit = SiteSettings.get().mailbox_limit
        if limit > 0:
            count = MailboxArtifact.objects.filter(user=request.user).count()
            if count >= limit:
                return Response(
                    {"detail": f"Mailbox limit of {limit} document(s) reached. Delete some documents to generate new ones."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            item = Item.objects.get(
                pk=item_id, item_type__vault=self.current_vault
            )
        except (Item.DoesNotExist, ValueError, ValidationError):
            return Response(
                {"detail": "Item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        content = generate_markdown(item_id, vault=self.current_vault)
        filename = f"{item.title}.md"

        artifact = MailboxArtifact.objects.create(
            user=request.user,
            vault=getattr(request.user, "active_vault", None),
            filename=filename,
            content=content,
            file_size=len(content.encode("utf-8")),
            source_item=item,
        )

        serializer = MailboxArtifactSerializer(artifact)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
