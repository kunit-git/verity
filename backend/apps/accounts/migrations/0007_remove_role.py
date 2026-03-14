# Remove the old global role field from User after data migration.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_add_is_site_admin_remove_role"),
        ("vaults", "0004_migrate_roles"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
    ]
