from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EDITOR,
    )

    class Meta:
        db_table = "accounts_user"


class SiteSettings(models.Model):
    """Singleton model for site-wide configuration."""

    registration_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "accounts_sitesettings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
