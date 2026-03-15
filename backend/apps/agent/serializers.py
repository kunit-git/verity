from rest_framework import serializers

from .models import Conversation, Message, PendingAction


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "role",
            "content",
            "tool_calls",
            "tool_call_id",
            "tool_name",
            "created_at",
        ]
        read_only_fields = fields


class PendingActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingAction
        fields = [
            "id",
            "action_type",
            "payload",
            "status",
            "result",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields


class ConversationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "context_item",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ConversationDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    pending_actions = PendingActionSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "title",
            "context_item",
            "messages",
            "pending_actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ConversationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "context_item"]
        read_only_fields = ["id"]

    def validate_context_item(self, value):
        if value and value.item_type.vault_id != self.context["vault"].id:
            raise serializers.ValidationError("Item does not belong to this vault.")
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["user"]
        validated_data["vault"] = self.context["vault"]
        return super().create(validated_data)


class ChatInputSerializer(serializers.Serializer):
    message = serializers.CharField()
