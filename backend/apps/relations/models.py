import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class RelationType(models.Model):
    class Kind(models.TextChoices):
        COMPOSITION = "composition", "Composition"
        TRACE = "trace", "Trace"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=100, unique=True)
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

    def __str__(self):
        return self.name


class ItemRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    relation_type = models.ForeignKey(
        RelationType, on_delete=models.PROTECT, related_name="relations"
    )
    source = models.ForeignKey(
        "items.Item", on_delete=models.CASCADE, related_name="outgoing_relations"
    )
    target = models.ForeignKey(
        "items.Item", on_delete=models.CASCADE, related_name="incoming_relations"
    )
    source_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Pin source to this version number. NULL = latest.",
    )
    target_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Pin target to this version number. NULL = latest.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "relations_item_relation"
        unique_together = [("relation_type", "source", "target")]
        ordering = ["position", "created_at"]

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
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source} --[{self.relation_type}]--> {self.target}"
