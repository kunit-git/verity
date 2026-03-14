import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import SoftDeleteModel


class RelationType(SoftDeleteModel):
    class Kind(models.TextChoices):
        COMPOSITION = "composition", "Composition"
        TRACE = "trace", "Trace"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        "vaults.Vault", on_delete=models.PROTECT, related_name="relation_types",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=100)
    forward_label = models.CharField(max_length=100)
    reverse_label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    source_item_type = models.ForeignKey(
        "items.ItemType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_relation_types",
        help_text="Item type allowed as source. NULL means any type.",
    )
    target_item_type = models.ForeignKey(
        "items.ItemType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="target_relation_types",
        help_text="Item type allowed as target. NULL means any type.",
    )
    is_builtin = models.BooleanField(
        default=False,
        help_text="Built-in relation types cannot be deleted.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "relations_relation_type"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["vault", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_relation_type_name",
            ),
        ]

    def __str__(self):
        return self.name


class ItemRelation(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    relation_type = models.ForeignKey(
        RelationType, on_delete=models.PROTECT, related_name="relations"
    )
    source = models.ForeignKey(
        "items.Item", on_delete=models.PROTECT, related_name="outgoing_relations"
    )
    target = models.ForeignKey(
        "items.Item", on_delete=models.PROTECT, related_name="incoming_relations"
    )
    source_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Pin source to this version number. NULL = latest.",
    )
    target_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Pin target to this version number. NULL = latest.",
    )
    version_pinned = models.BooleanField(
        default=False,
        help_text="User explicitly reviewed and chose to keep older version reference.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "relations_item_relation"
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["relation_type", "source", "target"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_item_relation",
            ),
        ]

    def clean(self):
        from apps.items.models import ItemVersion

        if self.source_id == self.target_id:
            raise ValidationError("An item cannot relate to itself.")
        if self.relation_type_id:
            rt = self.relation_type
            if rt.source_item_type_id and self.source.item_type_id != rt.source_item_type_id:
                raise ValidationError(
                    f"Source item must be of type '{rt.source_item_type.name}'."
                )
            if rt.target_item_type_id and self.target.item_type_id != rt.target_item_type_id:
                raise ValidationError(
                    f"Target item must be of type '{rt.target_item_type.name}'."
                )
        if self.source_version is not None:
            # current_version is always valid (no snapshot exists for unedited items)
            if self.source_version != self.source.current_version and not ItemVersion.objects.filter(
                item_id=self.source_id, version_number=self.source_version
            ).exists():
                raise ValidationError(
                    {"source_version": f"Version {self.source_version} does not exist for the source item."}
                )
        if self.target_version is not None:
            if self.target_version != self.target.current_version and not ItemVersion.objects.filter(
                item_id=self.target_id, version_number=self.target_version
            ).exists():
                raise ValidationError(
                    {"target_version": f"Version {self.target_version} does not exist for the target item."}
                )

    def save(self, *args, **kwargs):
        # Auto-set versions on creation so suspect-link tracking always works
        if self._state.adding:
            if self.source_version is None and self.source_id:
                self.source_version = self.source.current_version
            if self.target_version is None and self.target_id:
                self.target_version = self.target.current_version
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source} --[{self.relation_type}]--> {self.target}"
