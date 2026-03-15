from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from apps.relations.models import RelationType
from apps.vaults.models import Vault


class Command(BaseCommand):
    help = "Seed built-in relation types for all existing vaults"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Drop and recreate the database before seeding (destroys all data)",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset_database()

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

    def _reset_database(self):
        """Drop and recreate the database, then run migrations."""
        db_settings = settings.DATABASES["default"]
        db_name = db_settings["NAME"]
        db_user = db_settings["USER"]
        db_password = db_settings["PASSWORD"]
        db_host = db_settings["HOST"]
        db_port = db_settings["PORT"]

        self.stdout.write(f"Resetting database '{db_name}'...")

        # Connect to the 'postgres' maintenance database to drop/create
        import psycopg

        conninfo = f"host={db_host} port={db_port} user={db_user} password={db_password} dbname=postgres"
        with psycopg.connect(conninfo, autocommit=True) as conn:
            # Terminate existing connections
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                [db_name],
            )
            conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            conn.execute(f'CREATE DATABASE "{db_name}" OWNER "{db_user}"')

        self.stdout.write(f"  Database '{db_name}' recreated.")

        # Re-establish Django's connection to the fresh database
        connection.close()

        # Run migrations
        self.stdout.write("  Running migrations...")
        call_command("migrate", verbosity=0)
        self.stdout.write("  Migrations complete.")
