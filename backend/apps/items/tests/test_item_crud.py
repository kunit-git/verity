import pytest
from conftest import ItemFactory, ItemTypeFactory, CustomFieldDefinitionFactory, VaultFactory, VaultMembershipFactory, UserFactory
from rest_framework.test import APIClient


URL = "/api/v1/items/"


def _auth(client, user):
    r = client.post("/api/v1/auth/login/", {"username": user.username, "password": "testpass123"}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return client


class TestItemList:
    def test_list(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(URL)
        assert r.status_code == 200
        assert r.data["count"] >= 1

    def test_filter_by_item_type(self, editor_client, item_type, editor_user, vault):
        other_type = ItemTypeFactory(vault=vault, slug="other-type")
        ItemFactory(item_type=item_type, created_by=editor_user)
        ItemFactory(item_type=other_type, created_by=editor_user)
        r = editor_client.get(f"{URL}?item_type__slug={item_type.slug}")
        assert r.status_code == 200
        assert r.data["count"] == 1

    def test_filter_by_status(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, status="draft")
        ItemFactory(item_type=item_type, created_by=editor_user, status="active")
        r = editor_client.get(f"{URL}?status=draft")
        assert r.data["count"] == 1

    def test_search(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="Searchable Item")
        ItemFactory(item_type=item_type, created_by=editor_user, title="Other")
        r = editor_client.get(f"{URL}?search=Searchable")
        assert r.data["count"] == 1

    def test_ordering(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user, title="BBB")
        ItemFactory(item_type=item_type, created_by=editor_user, title="AAA")
        r = editor_client.get(f"{URL}?ordering=title")
        assert r.data["results"][0]["title"] == "AAA"


class TestItemCreate:
    def test_create_basic(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "title": "New Item", "item_type": str(item_type.id),
        }, format="json")
        assert r.status_code == 201
        assert r.data["title"] == "New Item"
        assert r.data["current_version"] == 1

    def test_create_with_custom_fields(self, editor_client, item_type_with_fields):
        r = editor_client.post(URL, {
            "title": "With Fields",
            "item_type": str(item_type_with_fields.id),
            "custom_fields": {"priority": 5, "notes": "test"},
        }, format="json")
        assert r.status_code == 201
        assert r.data["custom_fields"]["priority"] == 5

    def test_missing_required_field(self, editor_client, item_type_with_fields):
        r = editor_client.post(URL, {
            "title": "Missing Required",
            "item_type": str(item_type_with_fields.id),
            "custom_fields": {"notes": "test"},
        }, format="json")
        assert r.status_code == 400

    def test_unknown_custom_field(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "title": "Unknown Field",
            "item_type": str(item_type.id),
            "custom_fields": {"nonexistent": "val"},
        }, format="json")
        assert r.status_code == 400

    def test_created_by_auto_set(self, editor_client, item_type, editor_user):
        r = editor_client.post(URL, {
            "title": "Auto Created By", "item_type": str(item_type.id),
        }, format="json")
        assert r.data["created_by"] == editor_user.pk

    def test_viewer_forbidden(self, viewer_client, item_type):
        r = viewer_client.post(URL, {
            "title": "Nope", "item_type": str(item_type.id),
        }, format="json")
        assert r.status_code == 403

    def test_cannot_create_with_item_type_from_another_vault(self, editor_client, db):
        """Passing an item_type UUID from a different vault must be rejected,
        preventing cross-vault item creation."""
        other_vault = VaultFactory()
        other_type = ItemTypeFactory(vault=other_vault)
        r = editor_client.post(URL, {
            "title": "Cross Vault", "item_type": str(other_type.id),
        }, format="json")
        assert r.status_code == 400


class TestItemDetail:
    def test_get(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"{URL}{item.id}/")
        assert r.status_code == 200
        assert r.data["title"] == item.title

    def test_patch(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.patch(f"{URL}{item.id}/", {
            "title": "Updated Title",
        }, format="json")
        assert r.status_code == 200
        assert r.data["title"] == "Updated Title"

    def test_delete(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.delete(f"{URL}{item.id}/")
        assert r.status_code == 204


class TestVaultScoping:
    def test_cross_vault_not_visible(self, editor_client, vault, editor_user):
        other_admin = UserFactory(is_site_admin=True)
        other_vault = VaultFactory(created_by=other_admin)
        other_type = ItemTypeFactory(vault=other_vault)
        ItemFactory(item_type=other_type, created_by=other_admin)
        r = editor_client.get(URL)
        assert r.data["count"] == 0
