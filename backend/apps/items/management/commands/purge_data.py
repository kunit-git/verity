"""
Management command: purge_data

Hard-deletes all user data from the database, then runs seed_data to
re-create the admin user, default vault, and built-in relation types.

Usage:
    python manage.py purge_data
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.items.models import (
    CustomFieldDefinition,
    CustomFieldValue,
    DocumentTemplate,
    Item,
    ItemType,
    ItemVersion,
)
from apps.mailbox.models import MailboxArtifact
from apps.matrices.models import Matrix, MatrixColumn
from apps.relations.models import ItemRelation, RelationType
from apps.vaults.models import Vault, VaultAuditLog, VaultMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Purge all data from the database, then re-run seed_data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the confirmation prompt",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["yes"]:
            confirm = input(
                "This will PERMANENTLY DELETE all data. Type 'yes' to continue: "
            )
            if confirm != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        self.stdout.write("Purging all data...")

        # Delete in dependency order (children before parents)
        MatrixColumn.all_objects.all().hard_delete()
        Matrix.all_objects.all().hard_delete()
        ItemRelation.all_objects.all().hard_delete()
        CustomFieldValue.all_objects.all().hard_delete()
        ItemVersion.all_objects.all().hard_delete()
        Item.all_objects.all().hard_delete()
        DocumentTemplate.all_objects.all().hard_delete()
        CustomFieldDefinition.all_objects.all().hard_delete()
        ItemType.all_objects.all().hard_delete()
        RelationType.all_objects.all().hard_delete()
        MailboxArtifact.all_objects.all().hard_delete()
        VaultAuditLog.objects.all().delete()
        VaultMembership.all_objects.all().hard_delete()
        Vault.all_objects.all().hard_delete()
        User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("  All data purged.\n"))

        self.stdout.write("Running seed_data...")
        call_command("seed_data")
