import uuid

from django.conf import settings
from django.db import models


class ItemType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "items_item_type"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomFieldDefinition(models.Model):
    class FieldKind(models.TextChoices):
        TEXT = "text"
        INTEGER = "integer"
        DECIMAL = "decimal"
        BOOLEAN = "boolean"
        DATE = "date"
        CHOICE = "choice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.ForeignKey(
        ItemType, on_delete=models.CASCADE, related_name="custom_fields"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    field_kind = models.CharField(max_length=20, choices=FieldKind.choices)
    is_required = models.BooleanField(default=False)
    options = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "items_custom_field_def"
        unique_together = [("item_type", "slug")]
        ordering = ["display_order"]

    def __str__(self):
        return f"{self.item_type.name}.{self.name}"


class Item(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        IN_REVIEW = "in_review", "In Review"
        APPROVED = "approved", "Approved"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.ForeignKey(
        ItemType, on_delete=models.PROTECT, related_name="items"
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_items",
    )
    current_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "items_item"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"[{self.item_type.slug}] {self.title}"


class ItemVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)
    custom_fields_snapshot = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    change_summary = models.TextField(blank=True)

    class Meta:
        db_table = "items_item_version"
        unique_together = [("item", "version_number")]
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.item} v{self.version_number}"


class CustomFieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="custom_field_values"
    )
    field_definition = models.ForeignKey(
        CustomFieldDefinition, on_delete=models.CASCADE
    )
    value = models.JSONField()

    class Meta:
        db_table = "items_custom_field_value"
        unique_together = [("item", "field_definition")]
