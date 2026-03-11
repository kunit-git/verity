from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        LOCKED = "locked", "Locked"
        DELETED = "deleted", "Deleted"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )

    class Meta:
        db_table = "accounts_user"


class SiteSettings(models.Model):
    """Singleton model for site-wide configuration."""

    registration_enabled = models.BooleanField(default=True)
    mailbox_limit = models.PositiveIntegerField(
        default=0,
        help_text="Maximum mailbox documents per user. 0 means unlimited.",
    )

    class Meta:
        db_table = "accounts_sitesettings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
