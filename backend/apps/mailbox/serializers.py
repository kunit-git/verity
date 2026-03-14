from rest_framework import serializers

from .models import MailboxArtifact


class MailboxArtifactSerializer(serializers.ModelSerializer):
    vault_name = serializers.CharField(
        source="vault.name", read_only=True, default=None
    )

    class Meta:
        model = MailboxArtifact
        fields = [
            "id",
            "filename",
            "file_size",
            "content_type",
            "source_item",
            "vault",
            "vault_name",
            "created_at",
        ]
        read_only_fields = fields


class MailboxArtifactDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailboxArtifact
        fields = [
            "id",
            "filename",
            "content",
            "file_size",
            "content_type",
            "source_item",
            "created_at",
        ]
        read_only_fields = fields
