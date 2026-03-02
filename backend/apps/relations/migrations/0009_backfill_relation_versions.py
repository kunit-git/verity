from django.db import migrations


def backfill_versions(apps, schema_editor):
    """Set source_version and target_version to each item's current_version
    for all existing relations where they are NULL."""
    ItemRelation = apps.get_model("relations", "ItemRelation")
    for rel in ItemRelation.objects.select_related("source", "target").filter(
        source_version__isnull=True
    ) | ItemRelation.objects.select_related("source", "target").filter(
        target_version__isnull=True
    ):
        changed = False
        if rel.source_version is None:
            rel.source_version = rel.source.current_version
            changed = True
        if rel.target_version is None:
            rel.target_version = rel.target.current_version
            changed = True
        if changed:
            rel.save(update_fields=["source_version", "target_version"])


class Migration(migrations.Migration):

    dependencies = [
        ("relations", "0008_itemrelation_source_version_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_versions, migrations.RunPython.noop),
    ]
