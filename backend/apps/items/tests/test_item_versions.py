import pytest
from conftest import ItemFactory
from apps.items.models import ItemVersion


class TestItemVersioning:
    def test_patch_increments_version(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        assert item.current_version == 1
        r = editor_client.patch(f"/api/v1/items/{item.id}/", {
            "title": "Updated",
        }, format="json")
        assert r.data["current_version"] == 2

    def test_patch_creates_snapshot(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="Original")
        editor_client.patch(f"/api/v1/items/{item.id}/", {
            "title": "Updated",
        }, format="json")
        snapshot = ItemVersion.objects.get(item=item, version_number=1)
        assert snapshot.title == "Original"

    def test_snapshot_includes_custom_fields(self, editor_client, item_type_with_fields, editor_user):
        r = editor_client.post("/api/v1/items/", {
            "title": "With CF",
            "item_type": str(item_type_with_fields.id),
            "custom_fields": {"priority": 5, "notes": "v1"},
        }, format="json")
        item_id = r.data["id"]
        editor_client.patch(f"/api/v1/items/{item_id}/", {
            "title": "Updated CF",
            "custom_fields": {"priority": 10, "notes": "v2"},
        }, format="json")
        snapshot = ItemVersion.objects.get(item_id=item_id, version_number=1)
        assert snapshot.custom_fields_snapshot["priority"] == 5

    def test_multiple_patches(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="v1")
        editor_client.patch(f"/api/v1/items/{item.id}/", {"title": "v2"}, format="json")
        editor_client.patch(f"/api/v1/items/{item.id}/", {"title": "v3"}, format="json")
        item.refresh_from_db()
        assert item.current_version == 3
        assert ItemVersion.objects.filter(item=item).count() == 2


class TestVersionEndpoints:
    def test_list_versions(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        editor_client.patch(f"/api/v1/items/{item.id}/", {"title": "v2"}, format="json")
        r = editor_client.get(f"/api/v1/items/{item.id}/versions/")
        assert r.status_code == 200

    def test_get_specific_version(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="Original")
        editor_client.patch(f"/api/v1/items/{item.id}/", {"title": "v2"}, format="json")
        r = editor_client.get(f"/api/v1/items/{item.id}/versions/1/")
        assert r.status_code == 200
        assert r.data["title"] == "Original"

    def test_get_current_version(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="Current")
        r = editor_client.get(f"/api/v1/items/{item.id}/versions/1/")
        assert r.status_code == 200
        assert r.data["title"] == "Current"

    def test_nonexistent_version(self, editor_client, item_type, editor_user):
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{item.id}/versions/999/")
        assert r.status_code == 404
