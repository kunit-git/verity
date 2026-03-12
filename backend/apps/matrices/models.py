import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import SoftDeleteModel


class Matrix(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
        MatrixColumn.all_objects.filter(matrix=self, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )


class MatrixColumn(SoftDeleteModel):
    class Kind(models.TextChoices):
        SEED = "seed", "Seed"
        TRAVERSAL = "traversal", "Traversal"
        FORMULA = "formula", "Formula"

    class Direction(models.TextChoices):
        OUTGOING = "outgoing", "Outgoing"
        INCOMING = "incoming", "Incoming"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matrix = models.ForeignKey(
        Matrix, on_delete=models.PROTECT, related_name="columns"
    )
    position = models.PositiveIntegerField()
    label = models.CharField(max_length=200)
    column_kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.TRAVERSAL,
    )

    # Seed column fields (position == 0)
    seed_item_type = models.ForeignKey(
        "items.ItemType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matrix_seed_columns",
    )
    seed_container = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matrix_seed_container_columns",
    )

    # Traversal column fields (position > 0)
    relation_type = models.ForeignKey(
        "relations.RelationType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="matrix_columns",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        null=True,
        blank=True,
    )

    # Formula column fields
    formula = models.TextField(blank=True, default="")

    class Meta:
        db_table = "matrices_matrix_column"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["matrix", "position"],
                condition=models.Q(is_deleted=False),
                name="unique_alive_matrix_column_position",
            ),
        ]

    def __str__(self):
        return f"{self.matrix.name} col[{self.position}]: {self.label}"
