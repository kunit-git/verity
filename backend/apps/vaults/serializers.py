from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Vault, VaultAuditLog, VaultMembership

User = get_user_model()


class VaultSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source="created_by.username", read_only=True
    )
    locked_by_username = serializers.CharField(
        source="locked_by.username", read_only=True, default=None
    )
    member_count = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Vault
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "created_by",
            "created_by_username",
            "member_count",
            "is_locked",
            "locked_at",
            "locked_by",
            "locked_by_username",
            "created_at",
            "my_role",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "is_locked",
            "locked_at",
            "locked_by",
            "created_at",
        ]

    def get_member_count(self, obj):
        return VaultMembership.objects.filter(vault=obj).count()

    def get_my_role(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        if request.user.is_site_admin:
            return "admin"
        membership = VaultMembership.objects.filter(
            vault=obj, user=request.user
        ).values_list("role", flat=True).first()
        return membership

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class VaultMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    is_site_admin = serializers.BooleanField(source="user.is_site_admin", read_only=True)

    class Meta:
        model = VaultMembership
        fields = ["id", "vault", "user", "username", "email", "role", "is_site_admin", "created_at"]
        read_only_fields = ["id", "vault", "created_at"]


class VaultAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = VaultAuditLog
        fields = ["id", "vault", "event", "actor", "actor_username", "detail", "created_at"]
        read_only_fields = fields


class SelectVaultSerializer(serializers.Serializer):
    vault_id = serializers.UUIDField()
