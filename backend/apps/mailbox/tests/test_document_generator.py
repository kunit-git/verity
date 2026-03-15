import pytest
from conftest import ItemFactory, ItemTypeFactory, CustomFieldDefinitionFactory
from apps.items.models import CustomFieldValue, DocumentTemplate
from apps.relations.models import RelationType, ItemRelation
from apps.mailbox.document_generator import generate_markdown


class TestDocumentGenerator:
    def test_generates_heading_with_title(self, db, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="My Item")
        md = generate_markdown(item.id)
        assert "# My Item" in md

    def test_includes_custom_fields(self, db, item_type, editor_user, vault):
        field = CustomFieldDefinitionFactory(
            item_type=item_type, name="Priority", slug="priority", field_kind="integer",
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user)
        CustomFieldValue.objects.create(item=item, field_definition=field, value=5)
        md = generate_markdown(item.id)
        assert "Priority" in md
        assert "5" in md

    def test_recursive_children(self, db, item_type, editor_user, vault):
        comp = RelationType.objects.get(vault=vault, kind="composition")
        parent = ItemFactory(item_type=item_type, created_by=editor_user, title="Parent")
        child = ItemFactory(item_type=item_type, created_by=editor_user, title="Child")
        ItemRelation(relation_type=comp, source=parent, target=child, created_by=editor_user).save()
        md = generate_markdown(parent.id)
        assert "Parent" in md
        assert "Child" in md

    def test_custom_template(self, db, item_type, editor_user, vault):
        DocumentTemplate.objects.create(
            item_type=item_type,
            template="CUSTOM: {{title}} - {{status}}",
            updated_by=editor_user,
        )
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="Templated")
        md = generate_markdown(item.id)
        assert "CUSTOM: Templated - draft" in md

    def test_default_template_fallback(self, db, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user, title="Default")
        md = generate_markdown(item.id)
        # Default template includes type, status, version
        assert "Default" in md
        assert "Version" in md

    def test_handles_missing_item(self, db, vault):
        import uuid
        md = generate_markdown(uuid.uuid4())
        assert md == ""

    def test_handles_empty_description(self, db, item_type, editor_user, vault):
        item = ItemFactory(item_type=item_type, created_by=editor_user, description="")
        md = generate_markdown(item.id)
        assert item.title in md
