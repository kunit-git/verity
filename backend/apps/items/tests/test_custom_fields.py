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


    def test_create_mermaid_field(self, editor_client, item_type):
        r = editor_client.post(f"/api/v1/item-types/{item_type.id}/custom-fields/", {
            "name": "Architecture", "slug": "architecture", "field_kind": "mermaid", "display_order": 6,
        }, format="json")
        assert r.status_code == 201
        assert r.data["field_kind"] == "mermaid"

    def test_mermaid_field_value_roundtrip(self, editor_client, item_type, editor_user):
        from conftest import CustomFieldDefinitionFactory, ItemFactory
        field = CustomFieldDefinitionFactory(item_type=item_type, slug="diagram", field_kind="mermaid")
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        source = "graph TD\n    A --> B"
        r = editor_client.patch(f"/api/v1/items/{item.id}/", {
            "custom_fields": {"diagram": source}
        }, format="json")
        assert r.status_code == 200
        assert r.data["custom_fields"]["diagram"] == source

    def test_mermaid_field_in_editor_data(self, editor_client, item_type, editor_user):
        from conftest import CustomFieldDefinitionFactory, ItemFactory
        field = CustomFieldDefinitionFactory(item_type=item_type, slug="diagram", field_kind="mermaid")
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        r = editor_client.get(f"/api/v1/items/{item.id}/editor-data/")
        assert r.status_code == 200
        defs = r.data["items"][0]["custom_field_definitions"]
        assert any(d["slug"] == "diagram" and d["field_kind"] == "mermaid" for d in defs)

    def test_mermaid_field_versioned(self, editor_client, item_type, editor_user):
        from conftest import CustomFieldDefinitionFactory, ItemFactory
        from apps.items.models import ItemVersion
        CustomFieldDefinitionFactory(item_type=item_type, slug="diagram", field_kind="mermaid")
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        source_v1 = "graph TD\n    A --> B"
        editor_client.patch(f"/api/v1/items/{item.id}/", {
            "custom_fields": {"diagram": source_v1}
        }, format="json")
        item.refresh_from_db()
        assert item.current_version == 2
        snapshot = ItemVersion.objects.filter(item=item, version_number=1).first()
        assert snapshot is not None


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
