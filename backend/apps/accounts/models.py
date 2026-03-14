from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        LOCKED = "locked", "Locked"
        DELETED = "deleted", "Deleted"

    is_site_admin = models.BooleanField(default=False)
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )
    active_vault = models.ForeignKey(
        "vaults.Vault",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "accounts_user"

    def get_vault_role(self):
        """Return the user's effective role in their active vault."""
        if not hasattr(self, "_cached_vault_role"):
            if self.is_site_admin:
                self._cached_vault_role = "admin"
            elif self.active_vault_id:
                from apps.vaults.models import VaultMembership

                try:
                    m = VaultMembership.objects.get(
                        vault_id=self.active_vault_id, user=self
                    )
                    self._cached_vault_role = m.role
                except VaultMembership.DoesNotExist:
                    self._cached_vault_role = None
            else:
                self._cached_vault_role = None
        return self._cached_vault_role


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
