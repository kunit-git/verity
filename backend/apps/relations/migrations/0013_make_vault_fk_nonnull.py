import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("relations", "0012_add_vault_fk_nullable"),
        ("vaults", "0002_create_default_vault"),
    ]

    operations = [
        migrations.AlterField(
            model_name="relationtype",
            name="vault",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="relation_types",
                to="vaults.vault",
            ),
        ),
    ]
