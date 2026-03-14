import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel


class Vault(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_vaults",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        db_table = "vaults_vault"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_vault_name",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_vault_slug",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self._create_builtin_relation_types()

    def _create_builtin_relation_types(self):
        from apps.relations.models import RelationType

        builtins = [
            {
                "kind": "composition",
                "name": "is_composed_of",
                "forward_label": "is composed of",
                "reverse_label": "is part of",
                "description": "Composition hierarchy \u2014 any item can own children.",
                "is_builtin": True,
            },
            {
                "kind": "trace",
                "name": "traces_to",
                "forward_label": "traces to",
                "reverse_label": "is traced from",
                "description": "Generic traceability link.",
                "is_builtin": True,
            },
        ]
        for data in builtins:
            RelationType.objects.create(vault=self, **data)

    def _soft_cascade(self):
        now = timezone.now()
        VaultMembership.all_objects.filter(
            vault=self, is_deleted=False
        ).update(is_deleted=True, deleted_at=now)


class VaultMembership(SoftDeleteModel):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        Vault, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vault_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vaults_vault_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["vault", "user"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_vault_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user} in {self.vault}"


class VaultAuditLog(models.Model):
    class Event(models.TextChoices):
        VAULT_CREATED = "vault_created", "Vault Created"
        MEMBER_ADDED = "member_added", "Member Added"
        MEMBER_REMOVED = "member_removed", "Member Removed"
        MEMBER_ROLE_CHANGED = "member_role_changed", "Member Role Changed"
        VAULT_LOCKED = "vault_locked", "Vault Locked"
        VAULT_UNLOCKED = "vault_unlocked", "Vault Unlocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        Vault, on_delete=models.PROTECT, related_name="audit_logs"
    )
    event = models.CharField(max_length=30, choices=Event.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "vaults_vault_audit_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event} on {self.vault} by {self.actor}"
