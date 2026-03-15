import pytest
from conftest import CustomFieldDefinitionFactory


class TestTemplate:
    def test_get_no_template(self, editor_client, item_type):
        r = editor_client.get(f"/api/v1/item-types/{item_type.id}/template/")
        assert r.status_code == 200
        assert r.data["template"] is None
        assert "available_fields" in r.data
        assert "heading" in r.data["available_fields"]
        assert "title" in r.data["available_fields"]

    def test_get_includes_custom_field_slugs(self, editor_client, item_type):
        CustomFieldDefinitionFactory(item_type=item_type, slug="my-field")
        r = editor_client.get(f"/api/v1/item-types/{item_type.id}/template/")
        assert "my-field" in r.data["available_fields"]

    def test_put_creates_template(self, editor_client, item_type):
        r = editor_client.put(
            f"/api/v1/item-types/{item_type.id}/template/",
            {"template": "# {{title}}"},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["template"] == "# {{title}}"

    def test_put_updates_template(self, editor_client, item_type):
        editor_client.put(
            f"/api/v1/item-types/{item_type.id}/template/",
            {"template": "# {{title}}"},
            format="json",
        )
        r = editor_client.put(
            f"/api/v1/item-types/{item_type.id}/template/",
            {"template": "## {{title}} v2"},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["template"] == "## {{title}} v2"

    def test_delete_template(self, editor_client, item_type):
        editor_client.put(
            f"/api/v1/item-types/{item_type.id}/template/",
            {"template": "# {{title}}"},
            format="json",
        )
        r = editor_client.delete(f"/api/v1/item-types/{item_type.id}/template/")
        assert r.status_code == 204

    def test_viewer_cannot_put(self, viewer_client, item_type):
        r = viewer_client.put(
            f"/api/v1/item-types/{item_type.id}/template/",
            {"template": "# {{title}}"},
            format="json",
        )
        assert r.status_code == 403
