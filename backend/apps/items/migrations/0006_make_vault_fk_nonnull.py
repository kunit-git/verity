import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0005_add_vault_fk_nullable"),
        ("vaults", "0002_create_default_vault"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemtype",
            name="vault",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="item_types",
                to="vaults.vault",
            ),
        ),
    ]
