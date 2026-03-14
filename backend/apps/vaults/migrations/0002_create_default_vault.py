"""
Data migration: create Default vault, backfill all existing data,
create memberships for all users, and set active_vault.
"""
import uuid

from django.db import migrations


DEFAULT_VAULT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def create_default_vault(apps, schema_editor):
    Vault = apps.get_model("vaults", "Vault")
    VaultMembership = apps.get_model("vaults", "VaultMembership")
    User = apps.get_model("accounts", "User")
    ItemType = apps.get_model("items", "ItemType")
    RelationType = apps.get_model("relations", "RelationType")
    Matrix = apps.get_model("matrices", "Matrix")
    MailboxArtifact = apps.get_model("mailbox", "MailboxArtifact")

    # Find an admin user to be the vault creator, or first user
    admin_user = User.objects.filter(role="admin").first()
    if not admin_user:
        admin_user = User.objects.first()
    if not admin_user:
        # No users exist — nothing to migrate
        return

    # Create the default vault (skip model save() hook, use raw create)
    vault = Vault.objects.create(
        id=DEFAULT_VAULT_ID,
        name="Default",
        slug="default",
        description="Default vault for existing data.",
        created_by=admin_user,
    )

    # Backfill vault FK on all existing records
    ItemType.objects.filter(vault__isnull=True).update(vault=vault)
    RelationType.objects.filter(vault__isnull=True).update(vault=vault)
    Matrix.objects.filter(vault__isnull=True).update(vault=vault)
    MailboxArtifact.objects.filter(vault__isnull=True).update(vault=vault)

    # Create memberships for all users
    for user in User.objects.all():
        VaultMembership.objects.create(vault=vault, user=user)
        # Set active vault
        User.objects.filter(pk=user.pk).update(active_vault=vault)


def reverse_default_vault(apps, schema_editor):
    Vault = apps.get_model("vaults", "Vault")
    VaultMembership = apps.get_model("vaults", "VaultMembership")
    User = apps.get_model("accounts", "User")
    ItemType = apps.get_model("items", "ItemType")
    RelationType = apps.get_model("relations", "RelationType")
    Matrix = apps.get_model("matrices", "Matrix")
    MailboxArtifact = apps.get_model("mailbox", "MailboxArtifact")

    # Clear vault FKs
    User.objects.all().update(active_vault=None)
    ItemType.objects.all().update(vault=None)
    RelationType.objects.all().update(vault=None)
    Matrix.objects.all().update(vault=None)
    MailboxArtifact.objects.all().update(vault=None)

    VaultMembership.objects.all().delete()
    Vault.objects.filter(id=DEFAULT_VAULT_ID).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("vaults", "0001_add_vault_fk_nullable"),
        ("accounts", "0005_add_vault_fk_nullable"),
        ("items", "0005_add_vault_fk_nullable"),
        ("relations", "0012_add_vault_fk_nullable"),
        ("matrices", "0005_add_vault_fk_nullable"),
        ("mailbox", "0003_add_vault_fk_nullable"),
    ]

    operations = [
        migrations.RunPython(create_default_vault, reverse_default_vault),
    ]
