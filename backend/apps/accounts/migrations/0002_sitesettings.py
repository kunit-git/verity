from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("registration_enabled", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "accounts_sitesettings",
            },
        ),
    ]
