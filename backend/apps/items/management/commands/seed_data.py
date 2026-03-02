from django.core.management.base import BaseCommand

from apps.relations.models import RelationType


class Command(BaseCommand):
    help = "Seed built-in relation types required for the system to function"

    def handle(self, *args, **options):
        # Remove deprecated types
        removed, _ = RelationType.objects.filter(name="is_aggregation_of").delete()
        if removed:
            self.stdout.write("  Removed: deprecated RelationType 'is_aggregation_of'")

        from apps.items.models import ItemType

        removed, _ = ItemType.objects.filter(slug="container").delete()
        if removed:
            self.stdout.write("  Removed: deprecated ItemType 'Container'")

        # Built-in relation types
        relation_types = [
            ("composition", "is_composed_of", "is composed of", "is part of", "Composition hierarchy — any item can own children."),
            ("trace", "traces_to", "traces to", "is traced from", "Generic traceability link."),
        ]

        for kind, name, fwd, rev, desc in relation_types:
            obj, created = RelationType.objects.get_or_create(
                name=name,
                defaults={
                    "kind": kind,
                    "forward_label": fwd,
                    "reverse_label": rev,
                    "description": desc,
                    "is_builtin": True,
                },
            )
            if not created:
                obj.kind = kind
                obj.is_builtin = True
                obj.save(update_fields=["kind", "is_builtin"])
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status}: RelationType '{name}'")

        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully."))
