from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import SiteSettings

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    active_vault_name = serializers.CharField(
        source="active_vault.name", read_only=True, default=None
    )
    active_vault_locked = serializers.BooleanField(
        source="active_vault.is_locked", read_only=True, default=False
    )
    vault_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_site_admin",
            "vault_role",
            "date_joined",
            "active_vault",
            "active_vault_name",
            "active_vault_locked",
        ]
        read_only_fields = [
            "id",
            "is_site_admin",
            "vault_role",
            "date_joined",
            "active_vault",
            "active_vault_name",
            "active_vault_locked",
        ]

    def get_vault_role(self, obj):
        return obj.get_vault_role()


class UserManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_site_admin",
            "date_joined",
            "account_status",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "date_joined",
            "account_status",
            "is_active",
        ]


class ChangeOwnPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class AdminChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, min_length=8)


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ["registration_enabled", "mailbox_limit"]
