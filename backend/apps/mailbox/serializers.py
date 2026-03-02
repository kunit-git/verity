from rest_framework import serializers

from .models import MailboxArtifact


class MailboxArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailboxArtifact
        fields = [
            "id",
            "filename",
            "file_size",
            "content_type",
            "source_item",
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
