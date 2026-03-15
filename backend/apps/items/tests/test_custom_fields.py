import pytest
from conftest import CustomFieldDefinitionFactory


class TestCustomFieldCreate:
    def test_create_text_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Notes", "slug": "notes", "field_kind": "text", "display_order": 0,
        }, format="json")
        assert r.status_code == 201
        assert r.data["field_kind"] == "text"

    def test_create_integer_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Priority", "slug": "priority", "field_kind": "integer", "display_order": 1,
        }, format="json")
        assert r.status_code == 201

    def test_create_choice_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Status", "slug": "status-field", "field_kind": "choice",
            "options": {"choices": ["low", "medium", "high"]}, "display_order": 2,
        }, format="json")
        assert r.status_code == 201

    def test_create_boolean_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Active", "slug": "active", "field_kind": "boolean", "display_order": 3,
        }, format="json")
        assert r.status_code == 201

    def test_create_decimal_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Weight", "slug": "weight", "field_kind": "decimal", "display_order": 4,
        }, format="json")
        assert r.status_code == 201

    def test_create_date_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Due Date", "slug": "due-date", "field_kind": "date", "display_order": 5,
        }, format="json")
        assert r.status_code == 201

    def test_duplicate_slug(self, editor_client, item_type):
        CustomFieldDefinitionFactory(item_type=item_type, slug="dup")
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Dup", "slug": "dup", "field_kind": "text", "display_order": 0,
        }, format="json")
        assert r.status_code == 400

    def test_viewer_forbidden(self, viewer_client, item_type):
        r = viewer_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Nope", "slug": "nope", "field_kind": "text", "display_order": 0,
        }, format="json")
        assert r.status_code == 403


class TestCustomFieldManage:
    def test_patch_field(self, editor_client, item_type):
        field = CustomFieldDefinitionFactory(item_type=item_type, slug="editable")
        r = editor_client.patch(
            f"/api/v1/item-types/{item_type.id}/custom-fields/{field.id}/",
            {"name": "Renamed"},
            format="json",
        )
        assert r.status_code == 200
        assert r.data["name"] == "Renamed"

    def test_delete_field(self, editor_client, item_type):
        field = CustomFieldDefinitionFactory(item_type=item_type, slug="deletable")
        r = editor_client.delete(
            f"/api/v1/item-types/{item_type.id}/custom-fields/{field.id}/"
        )
        assert r.status_code == 204
