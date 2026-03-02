from django.db import migrations


def populate_kind(apps, schema_editor):
    RelationType = apps.get_model("relations", "RelationType")
    RelationType.objects.filter(name="is_composed_of").update(kind="composition")
    # All others default to "trace" which is already set by the field default


class Migration(migrations.Migration):
    dependencies = [
        ("relations", "0004_add_kind_to_relationtype"),
    ]

    operations = [
        migrations.RunPython(populate_kind, migrations.RunPython.noop),
    ]
