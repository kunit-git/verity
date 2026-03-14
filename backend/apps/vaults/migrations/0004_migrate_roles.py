"""
Data migration: copy User.role → VaultMembership.role for all memberships,
and set User.is_site_admin=True where User.role == 'admin'.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    VaultMembership = apps.get_model("vaults", "VaultMembership")

    # Set is_site_admin for all admin users
    User.objects.filter(role="admin").update(is_site_admin=True)

    # Copy user roles to their vault memberships
    for membership in VaultMembership.objects.select_related("user").filter(is_deleted=False):
        membership.role = membership.user.role
        membership.save(update_fields=["role"])


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    VaultMembership = apps.get_model("vaults", "VaultMembership")

    # Restore role field from is_site_admin
    User.objects.filter(is_site_admin=True).update(role="admin")

    # For non-admins, pick the highest role from their memberships
    for user in User.objects.filter(is_site_admin=False):
        memberships = VaultMembership.objects.filter(user=user, is_deleted=False)
        roles = set(memberships.values_list("role", flat=True))
        if "admin" in roles:
            user.role = "admin"
        elif "editor" in roles:
            user.role = "editor"
        else:
            user.role = "viewer"
        user.save(update_fields=["role"])


class Migration(migrations.Migration):

    dependencies = [
        ("vaults", "0003_add_role_to_membership"),
        ("accounts", "0006_add_is_site_admin_remove_role"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
