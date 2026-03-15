import pytest
from conftest import ItemTypeFactory, ItemFactory


URL = "/api/v1/item-types/"


class TestItemTypeList:
    def test_list(self, editor_client, item_type):
        r = editor_client.get(URL)
        assert r.status_code == 200
        assert r.data["count"] >= 1

    def test_includes_item_count(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(URL)
        assert r.status_code == 200
        found = [t for t in r.data["results"] if t["id"] == str(item_type.id)]
        assert found[0]["item_count"] == 1

    def test_viewer_can_read(self, viewer_client, item_type):
        r = viewer_client.get(URL)
        assert r.status_code == 200

    def test_unauthenticated_forbidden(self, api_client, db):
        r = api_client.get(URL)
        assert r.status_code == 401


class TestItemTypeCreate:
    def test_create(self, editor_client, vault):
        r = editor_client.post(URL, {
            "name": "Requirement", "slug": "req",
        }, format="json")
        assert r.status_code == 201
        assert r.data["name"] == "Requirement"

    def test_duplicate_name(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "name": item_type.name, "slug": "diff",
        }, format="json")
        assert r.status_code == 400

    def test_duplicate_slug(self, editor_client, item_type):
        r = editor_client.post(URL, {
            "name": "Different", "slug": item_type.slug,
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client):
        r = viewer_client.post(URL, {
            "name": "Nope", "slug": "nope",
        }, format="json")
        assert r.status_code == 403


class TestItemTypeUpdate:
    def test_patch(self, editor_client, item_type):
        r = editor_client.patch(f"{URL}{item_type.id}/", {
            "description": "Updated",
        }, format="json")
        assert r.status_code == 200
        assert r.data["description"] == "Updated"


class TestItemTypeDelete:
    def test_delete_empty_type(self, editor_client, item_type):
        r = editor_client.delete(f"{URL}{item_type.id}/")
        assert r.status_code == 204

    def test_delete_with_items_409(self, editor_client, item_type, editor_user):
        ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.delete(f"{URL}{item_type.id}/")
        assert r.status_code == 409

    def test_viewer_forbidden(self, viewer_client, item_type):
        r = viewer_client.delete(f"{URL}{item_type.id}/")
        assert r.status_code == 403
