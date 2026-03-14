from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.relations.models import RelationType
from apps.vaults.models import Vault, VaultMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Seed built-in data: admin user, default vault, and relation types"

    def handle(self, *args, **options):
        # Remove deprecated types
        removed, _ = RelationType.all_objects.filter(name="is_aggregation_of").hard_delete()
        if removed:
            self.stdout.write("  Removed: deprecated RelationType 'is_aggregation_of'")

        from apps.items.models import ItemType

        removed, _ = ItemType.all_objects.filter(slug="container").hard_delete()
        if removed:
            self.stdout.write("  Removed: deprecated ItemType 'Container'")

        # Ensure admin user exists
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_site_admin": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("admin")
            admin.save(update_fields=["password"])
            self.stdout.write("  Created: admin user (admin / admin)")
        else:
            self.stdout.write("  Exists: admin user")

        # Ensure default vault exists
        vault, created = Vault.objects.get_or_create(
            slug="default",
            defaults={
                "name": "Default",
                "description": "Default vault.",
                "created_by": admin,
            },
        )
        if created:
            self.stdout.write("  Created: Default vault")
        else:
            self.stdout.write("  Exists: Default vault")

        # Ensure admin is a member and has active vault
        VaultMembership.objects.get_or_create(vault=vault, user=admin)
        if not admin.active_vault_id:
            admin.active_vault = vault
            admin.save(update_fields=["active_vault"])

        # Built-in relation types — ensure each vault has them
        relation_types = [
            ("composition", "is_composed_of", "is composed of", "is part of", "Composition hierarchy \u2014 any item can own children."),
            ("trace", "traces_to", "traces to", "is traced from", "Generic traceability link."),
        ]

        for v in Vault.objects.all():
            self.stdout.write(f"  Vault: {v.name}")
            for kind, name, fwd, rev, desc in relation_types:
                obj, created = RelationType.objects.get_or_create(
                    vault=v,
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
                self.stdout.write(f"    {status}: RelationType '{name}'")

        self.stdout.write(self.style.SUCCESS("Seed data loaded successfully."))
