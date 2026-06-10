import pytest
from conftest import (
    UserFactory,
    ItemFactory,
    ItemTypeFactory,
    VaultFactory,
    MailboxArtifactFactory,
)
from apps.accounts.models import SiteSettings
from apps.mailbox.models import MailboxArtifact
from rest_framework.test import APIClient


URL = "/api/v1/mailbox/"


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestMailboxList:
    def test_shows_only_own_artifacts(self, editor_client, editor_user, db):
        MailboxArtifactFactory(user=editor_user)
        other_user = UserFactory()
        MailboxArtifactFactory(user=other_user)
        r = editor_client.get(URL)
        assert r.status_code == 200
        assert r.data["count"] == 1

    def test_unauthenticated(self, api_client, db):
        r = api_client.get(URL)
        assert r.status_code == 401


class TestMailboxDetail:
    def test_get_includes_content(self, editor_client, editor_user, db):
        artifact = MailboxArtifactFactory(user=editor_user, content="# Hello")
        r = editor_client.get(f"{URL}{artifact.id}/")
        assert r.status_code == 200
        assert r.data["content"] == "# Hello"

    def test_other_users_artifact_not_found(self, editor_client, db):
        other = UserFactory()
        artifact = MailboxArtifactFactory(user=other)
        r = editor_client.get(f"{URL}{artifact.id}/")
        assert r.status_code == 404


class TestMailboxDelete:
    def test_delete(self, editor_client, editor_user, db):
        artifact = MailboxArtifactFactory(user=editor_user)
        r = editor_client.delete(f"{URL}{artifact.id}/")
        assert r.status_code == 204


class TestMailboxGenerate:
    def test_generate(self, editor_client, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.post(f"{URL}generate/", {
            "item_id": str(item.id),
        }, format="json")
        assert r.status_code == 201
        assert r.data["filename"] == f"{item.title}.md"
        assert r.data["file_size"] > 0

    def test_missing_item_id(self, editor_client):
        r = editor_client.post(f"{URL}generate/", {}, format="json")
        assert r.status_code == 400

    def test_nonexistent_item(self, editor_client):
        import uuid
        r = editor_client.post(f"{URL}generate/", {
            "item_id": str(uuid.uuid4()),
        }, format="json")
        assert r.status_code == 404

    def test_respects_mailbox_limit(self, editor_client, item_type, editor_user, vault):
        settings = SiteSettings.get()
        settings.mailbox_limit = 1
        settings.save()
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        # First should succeed
        r = editor_client.post(f"{URL}generate/", {"item_id": str(item.id)}, format="json")
        assert r.status_code == 201
        # Second should fail
        r = editor_client.post(f"{URL}generate/", {"item_id": str(item.id)}, format="json")
        assert r.status_code == 403

    def test_unlimited_when_zero(self, editor_client, item_type, editor_user, vault):
        settings = SiteSettings.get()
        settings.mailbox_limit = 0
        settings.save()
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        for _ in range(3):
            r = editor_client.post(f"{URL}generate/", {"item_id": str(item.id)}, format="json")
            assert r.status_code == 201

    def test_cannot_generate_for_item_in_another_vault(self, editor_client, db):
        """An editor must not be able to render an item from a vault they are
        not a member of (cross-vault IDOR)."""
        other_vault = VaultFactory()
        other_type = ItemTypeFactory(vault=other_vault)
        other_item = ItemFactory(item_type=other_type)
        r = editor_client.post(
            f"{URL}generate/", {"item_id": str(other_item.id)}, format="json"
        )
        assert r.status_code == 404
        # And nothing should have been written to the mailbox.
        assert not MailboxArtifact.objects.filter(source_item=other_item).exists()

    def test_generate_requires_active_vault(self, api_client, db):
        """A user with no active vault cannot generate documents."""
        user = UserFactory()
        api_client.force_authenticate(user=user)
        item = ItemFactory()
        r = api_client.post(f"{URL}generate/", {"item_id": str(item.id)}, format="json")
        assert r.status_code == 403
