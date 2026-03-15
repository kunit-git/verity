import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel


class Matrix(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        "vaults.Vault", on_delete=models.PROTECT, related_name="matrices",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_matrices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matrices_matrix"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    def _soft_cascade(self):
        MatrixSource.all_objects.filter(matrix=self, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )
        MatrixDisplayColumn.all_objects.filter(matrix=self, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )
        MatrixAnnotation.all_objects.filter(matrix=self, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )


class MatrixSource(SoftDeleteModel):
    """A data source in a matrix — defines how to fetch or compute data."""

    class Kind(models.TextChoices):
        SEED = "seed", "Seed"
        TRAVERSAL = "traversal", "Traversal"
        FORMULA = "formula", "Formula"
        ANNOTATION = "annotation", "Annotation"
        ITEM_FIELD = "item_field", "Item Field"

    class Direction(models.TextChoices):
        OUTGOING = "outgoing", "Outgoing"
        INCOMING = "incoming", "Incoming"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matrix = models.ForeignKey(
        Matrix, on_delete=models.PROTECT, related_name="sources"
    )
    name = models.SlugField(max_length=100)
    position = models.PositiveIntegerField()
    kind = models.CharField(max_length=15, choices=Kind.choices)

    # Seed fields
    seed_item_type = models.ForeignKey(
        "items.ItemType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matrix_seed_sources",
    )
    seed_container = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matrix_seed_container_sources",
    )

    # Traversal fields
    relation_type = models.ForeignKey(
        "relations.RelationType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matrix_sources",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        null=True,
        blank=True,
    )

    # Formula fields
    formula = models.TextField(blank=True, default="")

    # Item_field fields
    source_ref = models.SlugField(
        max_length=100, blank=True, default="",
        help_text="Name of the source whose items to read the field from",
    )
    field_slug = models.SlugField(
        max_length=100, blank=True, default="",
        help_text="Custom field slug to display",
    )

    class Meta:
        db_table = "matrices_matrix_source"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "name"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_matrix_source_name",
            ),
            models.UniqueConstraint(
                fields=["matrix", "position"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_matrix_source_position",
            ),
        ]

    def __str__(self):
        return f"{self.matrix.name} src[{self.position}]: {self.name}"


class MatrixDisplayColumn(SoftDeleteModel):
    """A display column in a matrix — references a source by name."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matrix = models.ForeignKey(
        Matrix, on_delete=models.PROTECT, related_name="display_columns"
    )
    position = models.PositiveIntegerField()
    heading = models.CharField(max_length=200)
    source_name = models.SlugField(max_length=100)

    class Meta:
        db_table = "matrices_matrix_display_column"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "position"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_matrix_display_column_position",
            ),
        ]

    def __str__(self):
        return f"{self.matrix.name} col[{self.position}]: {self.heading}"


class MatrixAnnotation(SoftDeleteModel):
    """Stores user-entered annotation values for annotation columns in a global matrix."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matrix = models.ForeignKey(
        Matrix, on_delete=models.PROTECT, related_name="annotations"
    )
    # Slug of the annotation MatrixColumn this value belongs to
    column_slug = models.SlugField(max_length=100)
    # SHA-256 hash of the ordered traversal+seed item IDs for the row
    row_hash = models.CharField(max_length=64, db_index=True)
    value = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_matrix_annotations",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matrices_matrix_annotation"
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "column_slug", "row_hash"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_matrix_annotation",
            ),
        ]

    def __str__(self):
        return f"MatrixAnnotation({self.matrix_id}, {self.column_slug}, {self.row_hash[:8]})"
