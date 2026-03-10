from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_sitesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="mailbox_limit",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Maximum mailbox documents per user. 0 means unlimited.",
            ),
        ),
    ]
