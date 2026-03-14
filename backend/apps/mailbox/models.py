import uuid

from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel


class MailboxArtifact(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mailbox_artifacts",
    )
    vault = models.ForeignKey(
        "vaults.Vault",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mailbox_artifacts",
    )
    filename = models.CharField(max_length=300)
    content = models.TextField()
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100, default="text/markdown")
    source_item = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mailbox_artifacts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mailbox_artifact"
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename
