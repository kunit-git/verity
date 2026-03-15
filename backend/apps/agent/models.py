import uuid

from django.conf import settings
from django.db import models

from apps.core.models import SoftDeleteModel


class Conversation(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="agent_conversations",
    )
    vault = models.ForeignKey(
        "vaults.Vault",
        on_delete=models.PROTECT,
        related_name="agent_conversations",
    )
    title = models.CharField(max_length=300, blank=True)
    context_item = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_conversation"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.id}"

    def _soft_cascade(self):
        from django.utils import timezone

        now = timezone.now()
        Message.all_objects.filter(conversation=self, is_deleted=False).update(
            is_deleted=True, deleted_at=now
        )
        PendingAction.all_objects.filter(conversation=self, is_deleted=False).update(
            is_deleted=True, deleted_at=now
        )


class Message(SoftDeleteModel):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"
        TOOL = "tool", "Tool"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField(blank=True)
    tool_calls = models.JSONField(default=list)
    tool_call_id = models.CharField(max_length=100, blank=True)
    tool_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_message"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:60]}"


class PendingAction(SoftDeleteModel):
    class ActionType(models.TextChoices):
        CREATE_ITEM = "create_item", "Create Item"
        UPDATE_ITEM = "update_item", "Update Item"
        CREATE_RELATION = "create_relation", "Create Relation"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXECUTED = "executed", "Executed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="pending_actions"
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_actions",
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    payload = models.JSONField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_pending_action"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.action_type} ({self.status})"
