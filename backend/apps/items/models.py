import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel


class ItemType(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "items_item_type"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_item_type_name",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_item_type_slug",
            ),
        ]

    def __str__(self):
        return self.name

    def _soft_cascade(self):
        now = timezone.now()
        field_ids = list(
            CustomFieldDefinition.all_objects.filter(
                item_type=self, is_deleted=False
            ).values_list("id", flat=True)
        )
        CustomFieldDefinition.all_objects.filter(
            item_type=self, is_deleted=False
        ).update(is_deleted=True, deleted_at=now)
        if field_ids:
            CustomFieldValue.all_objects.filter(
                field_definition_id__in=field_ids, is_deleted=False
            ).update(is_deleted=True, deleted_at=now)
        DocumentTemplate.all_objects.filter(
            item_type=self, is_deleted=False
        ).update(is_deleted=True, deleted_at=now)


class CustomFieldDefinition(SoftDeleteModel):
    class FieldKind(models.TextChoices):
        TEXT = "text"
        INTEGER = "integer"
        DECIMAL = "decimal"
        BOOLEAN = "boolean"
        DATE = "date"
        CHOICE = "choice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.ForeignKey(
        ItemType, on_delete=models.PROTECT, related_name="custom_fields"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    field_kind = models.CharField(max_length=20, choices=FieldKind.choices)
    is_required = models.BooleanField(default=False)
    options = models.JSONField(default=dict, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "items_custom_field_def"
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["item_type", "slug"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_custom_field_def_type_slug",
            ),
        ]

    def __str__(self):
        return f"{self.item_type.name}.{self.name}"

    def _soft_cascade(self):
        CustomFieldValue.all_objects.filter(
            field_definition=self, is_deleted=False
        ).update(is_deleted=True, deleted_at=timezone.now())


class Item(SoftDeleteModel):
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

    def _soft_cascade(self):
        from apps.relations.models import ItemRelation

        now = timezone.now()
        ItemVersion.all_objects.filter(item=self, is_deleted=False).update(
            is_deleted=True, deleted_at=now
        )
        CustomFieldValue.all_objects.filter(item=self, is_deleted=False).update(
            is_deleted=True, deleted_at=now
        )
        ItemRelation.all_objects.filter(
            models.Q(source=self) | models.Q(target=self),
            is_deleted=False,
        ).update(is_deleted=True, deleted_at=now)


class ItemVersion(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="versions")
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
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "version_number"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_item_version_number",
            ),
        ]

    def __str__(self):
        return f"{self.item} v{self.version_number}"


class DocumentTemplate(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_type = models.OneToOneField(
        ItemType, on_delete=models.PROTECT, related_name="document_template"
    )
    template = models.TextField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "items_document_template"
        constraints = [
            models.UniqueConstraint(
                fields=["item_type"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_document_template_item_type",
            ),
        ]

    def __str__(self):
        return f"Template for {self.item_type.name}"


class CustomFieldValue(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, related_name="custom_field_values"
    )
    field_definition = models.ForeignKey(
        CustomFieldDefinition, on_delete=models.PROTECT
    )
    value = models.JSONField()

    class Meta:
        db_table = "items_custom_field_value"
        constraints = [
            models.UniqueConstraint(
                fields=["item", "field_definition"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_custom_field_value_item_def",
            ),
        ]
