import uuid

from django.conf import settings
from django.db import models


class Matrix(models.Model):
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


class MatrixColumn(models.Model):
    class Direction(models.TextChoices):
        OUTGOING = "outgoing", "Outgoing"
        INCOMING = "incoming", "Incoming"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matrix = models.ForeignKey(
        Matrix, on_delete=models.CASCADE, related_name="columns"
    )
    position = models.PositiveIntegerField()
    label = models.CharField(max_length=200)

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

    class Meta:
        db_table = "matrices_matrix_column"
        unique_together = [("matrix", "position")]
        ordering = ["position"]

    def __str__(self):
        return f"{self.matrix.name} col[{self.position}]: {self.label}"
