import pytest
from conftest import ItemFactory, ItemRelationFactory, ItemTypeFactory, VaultMembershipFactory, UserFactory


@pytest.fixture
def root_item(item_type, editor_user):
    return ItemFactory(item_type=item_type, created_by=editor_user, title="Root Item")


@pytest.fixture
def child_item(item_type, editor_user, root_item, composition_type):
    child = ItemFactory(item_type=item_type, created_by=editor_user, title="Child Item")
    ItemRelationFactory(
        relation_type=composition_type,
        source=root_item,
        target=child,
        created_by=editor_user,
    )
    return child


class TestDocumentEditorData:
    def test_returns_root_item(self, editor_client, root_item):
        resp = editor_client.get(f"/api/v1/items/{root_item.id}/editor-data/")
        assert resp.status_code == 200
        items = resp.data["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(root_item.id)
        assert items[0]["depth"] == 1
        assert items[0]["title"] == root_item.title

    def test_includes_children_in_order(self, editor_client, root_item, child_item):
        resp = editor_client.get(f"/api/v1/items/{root_item.id}/editor-data/")
        assert resp.status_code == 200
        items = resp.data["items"]
        assert len(items) == 2
        assert items[0]["id"] == str(root_item.id)
        assert items[0]["depth"] == 1
        assert items[1]["id"] == str(child_item.id)
        assert items[1]["depth"] == 2

    def test_default_template_always_present(self, editor_client, root_item):
        resp = editor_client.get(f"/api/v1/items/{root_item.id}/editor-data/")
        assert resp.status_code == 200
        item = resp.data["items"][0]
        assert item["default_template"] is not None
        assert "{{title}}" in item["default_template"]
        assert item["template"] is None

    def test_custom_template_returned_when_set(self, editor_client, root_item):
        from apps.items.models import DocumentTemplate
        DocumentTemplate.objects.create(
            item_type=root_item.item_type,
            template="# {{title}}\n{{description}}",
            updated_by=root_item.created_by,
        )
        resp = editor_client.get(f"/api/v1/items/{root_item.id}/editor-data/")
        assert resp.status_code == 200
        item = resp.data["items"][0]
        assert item["template"] == "# {{title}}\n{{description}}"

    def test_custom_fields_included(self, editor_client, item_type_with_fields, editor_user, composition_type):
        from apps.items.models import CustomFieldValue, CustomFieldDefinition
        item = ItemFactory(item_type=item_type_with_fields, created_by=editor_user)
        priority_def = CustomFieldDefinition.objects.get(item_type=item_type_with_fields, slug="priority")
        CustomFieldValue.objects.create(item=item, field_definition=priority_def, value=5)

        resp = editor_client.get(f"/api/v1/items/{item.id}/editor-data/")
        assert resp.status_code == 200
        result = resp.data["items"][0]
        assert "priority" in result["custom_fields"]
        assert result["custom_fields"]["priority"] == 5
        cf_slugs = [cf["slug"] for cf in result["custom_field_definitions"]]
        assert "priority" in cf_slugs
        assert "notes" in cf_slugs

    def test_viewer_can_read(self, viewer_client, root_item):
        resp = viewer_client.get(f"/api/v1/items/{root_item.id}/editor-data/")
        assert resp.status_code == 200

    def test_returns_404_for_unknown_item(self, editor_client):
        resp = editor_client.get("/api/v1/items/00000000-0000-0000-0000-000000000000/editor-data/")
        assert resp.status_code == 404
