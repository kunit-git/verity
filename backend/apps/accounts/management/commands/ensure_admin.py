"""
Management command: ensure_admin

Idempotently provision a site admin using an explicitly supplied password.
The container entrypoint calls this only when a provisioning password is set;
otherwise use initial browser setup. An existing admin retains its password.
--recreate deletes and recreates the account and can fail on protected references.
Use Django changepassword for ordinary password recovery.

Credentials default to the standard ``DJANGO_SUPERUSER_*`` environment
variables so the same config drives ``createsuperuser`` and this command.

Usage:
    python manage.py ensure_admin
    python manage.py ensure_admin --recreate          # delete + recreate
    python manage.py ensure_admin --username me --password secret
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update the site admin (superuser) account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin"),
            help="Admin username (default: $DJANGO_SUPERUSER_USERNAME or 'admin').",
        )
        parser.add_argument(
            "--email",
            default=os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com"),
            help="Admin email (default: $DJANGO_SUPERUSER_EMAIL).",
        )
        parser.add_argument(
            "--password",
            default=os.environ.get("DJANGO_SUPERUSER_PASSWORD", ""),
            help="Admin password (default: $DJANGO_SUPERUSER_PASSWORD).",
        )
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Delete the existing admin (if any) and create it anew.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = options["password"]

        if not password:
            raise CommandError(
                "No admin password supplied. Set DJANGO_SUPERUSER_PASSWORD "
                "or pass --password."
            )

        existing = User.objects.filter(username=username).first()

        if existing and not existing.is_site_admin:
            raise CommandError(
                "An account with this username already exists and is not a site admin. "
                "Choose another username; existing users are never promoted automatically."
            )

        if existing and options["recreate"]:
            existing.delete()
            existing = None
            self.stdout.write(self.style.WARNING(f"Deleted existing admin '{username}'."))

        if existing:
            # Keep the account but make sure it still has full privileges.
            changed = False
            for attr in ("is_staff", "is_superuser", "is_site_admin"):
                if not getattr(existing, attr):
                    setattr(existing, attr, True)
                    changed = True
            if existing.email != email:
                existing.email = email
                changed = True
            if changed:
                existing.save()
            self.stdout.write(
                self.style.SUCCESS(f"Admin '{username}' already exists — left in place.")
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            is_site_admin=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Created admin '{username}'."))
