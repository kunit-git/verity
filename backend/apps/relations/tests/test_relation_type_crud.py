import pytest
from apps.relations.models import RelationType


URL = "/api/v1/relation-types/"


class TestRelationTypeList:
    def test_list_includes_builtins(self, editor_client, vault):
        r = editor_client.get(URL)
        assert r.status_code == 200
        names = [rt["name"] for rt in r.data["results"]]
        assert "is_composed_of" in names
        assert "traces_to" in names

    def test_viewer_can_read(self, viewer_client, vault):
        r = viewer_client.get(URL)
        assert r.status_code == 200


class TestRelationTypeCreate:
    def test_create(self, editor_client, vault):
        r = editor_client.post(URL, {
            "kind": "trace",
            "name": "verifies",
            "forward_label": "verifies",
            "reverse_label": "is verified by",
        }, format="json")
        assert r.status_code == 201
        assert r.data["name"] == "verifies"
        assert r.data["is_builtin"] is False

    def test_create_with_type_constraints(self, editor_client, vault, item_type):
        from conftest import ItemTypeFactory
        target_type = ItemTypeFactory(vault=vault, slug="target-type")
        r = editor_client.post(URL, {
            "kind": "trace",
            "name": "constrained",
            "forward_label": "links to",
            "reverse_label": "linked from",
            "source_item_type": str(item_type.id),
            "target_item_type": str(target_type.id),
        }, format="json")
        assert r.status_code == 201
        assert str(r.data["source_item_type"]) == str(item_type.id)

    def test_viewer_forbidden(self, viewer_client):
        r = viewer_client.post(URL, {
            "kind": "trace", "name": "nope",
            "forward_label": "x", "reverse_label": "y",
        }, format="json")
        assert r.status_code == 403


class TestRelationTypeDelete:
    def test_delete_custom(self, editor_client, vault):
        r = editor_client.post(URL, {
            "kind": "trace", "name": "deleteme",
            "forward_label": "x", "reverse_label": "y",
        }, format="json")
        rt_id = r.data["id"]
        r = editor_client.delete(f"{URL}{rt_id}/")
        assert r.status_code == 204

    def test_delete_builtin_forbidden(self, editor_client, vault):
        rt = RelationType.objects.get(vault=vault, name="is_composed_of")
        r = editor_client.delete(f"{URL}{rt.id}/")
        assert r.status_code == 403
