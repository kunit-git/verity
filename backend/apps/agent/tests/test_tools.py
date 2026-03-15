import pytest
from apps.agent.tools import (
    search_items,
    get_item_detail,
    get_item_children,
    get_item_relations,
    get_item_types,
    get_relation_types,
    create_item,
    update_item,
    create_relation,
)
from apps.agent.models import Conversation, Message, PendingAction
from conftest import (
    ItemFactory,
    ItemRelationFactory,
    VaultMembershipFactory,
)


@pytest.fixture
def conversation(vault, editor_user):
    return Conversation.objects.create(user=editor_user, vault=vault)


@pytest.fixture
def assistant_msg(conversation):
    return Message.objects.create(
        conversation=conversation, role="assistant", content="test"
    )


class TestReadTools:
    def test_search_items_by_query(self, vault, item_type, editor_user):
        ItemFactory(item_type=item_type, title="Widget Alpha", created_by=editor_user)
        ItemFactory(item_type=item_type, title="Gadget Beta", created_by=editor_user)
        result = search_items(vault, editor_user, query="Widget")
        assert len(result) == 1
        assert result[0]["title"] == "Widget Alpha"

    def test_search_items_by_type(self, vault, item_type, editor_user):
        ItemFactory(item_type=item_type, title="Item A", created_by=editor_user)
        result = search_items(vault, editor_user, item_type_slug=item_type.slug)
        assert len(result) == 1

    def test_search_items_by_status(self, vault, item_type, editor_user):
        ItemFactory(item_type=item_type, title="Draft", status="draft", created_by=editor_user)
        ItemFactory(item_type=item_type, title="Active", status="active", created_by=editor_user)
        result = search_items(vault, editor_user, status="active")
        assert len(result) == 1
        assert result[0]["title"] == "Active"

    def test_get_item_detail(self, vault, item_type, editor_user):
        item = ItemFactory(item_type=item_type, title="Detail Test", created_by=editor_user)
        result = get_item_detail(vault, editor_user, item_id=str(item.id))
        assert result["title"] == "Detail Test"
        assert result["item_type"] == item_type.slug
        assert "custom_fields" in result

    def test_get_item_children(self, vault, item_type, composition_type, editor_user):
        parent = ItemFactory(item_type=item_type, title="Parent", created_by=editor_user)
        child = ItemFactory(item_type=item_type, title="Child", created_by=editor_user)
        ItemRelationFactory(
            relation_type=composition_type,
            source=parent,
            target=child,
            created_by=editor_user,
        )
        result = get_item_children(vault, editor_user, item_id=str(parent.id))
        assert len(result) == 1
        assert result[0]["title"] == "Child"

    def test_get_item_relations(self, vault, item_type, trace_type, editor_user):
        a = ItemFactory(item_type=item_type, title="A", created_by=editor_user)
        b = ItemFactory(item_type=item_type, title="B", created_by=editor_user)
        ItemRelationFactory(
            relation_type=trace_type,
            source=a,
            target=b,
            created_by=editor_user,
        )
        result = get_item_relations(vault, editor_user, item_id=str(a.id))
        assert len(result["outgoing"]) == 1
        assert result["outgoing"][0]["target_title"] == "B"

        result_b = get_item_relations(vault, editor_user, item_id=str(b.id))
        assert len(result_b["incoming"]) == 1

    def test_get_item_types(self, vault, item_type, editor_user):
        result = get_item_types(vault, editor_user)
        slugs = [it["slug"] for it in result]
        assert item_type.slug in slugs

    def test_get_relation_types(self, vault, editor_user):
        result = get_relation_types(vault, editor_user)
        names = [rt["name"] for rt in result]
        assert "is_composed_of" in names
        assert "traces_to" in names


class TestWriteTools:
    def test_create_item_pending(self, conversation, assistant_msg, vault, editor_user, item_type):
        result = create_item(
            conversation, assistant_msg, vault, editor_user,
            item_type_slug=item_type.slug,
            title="New Requirement",
        )
        assert result["status"] == "pending"
        action = PendingAction.objects.get(pk=result["pending_action_id"])
        assert action.action_type == "create_item"
        assert action.payload["title"] == "New Requirement"

    def test_update_item_pending(self, conversation, assistant_msg, vault, editor_user, item_type):
        item = ItemFactory(item_type=item_type, title="Old Title", created_by=editor_user)
        result = update_item(
            conversation, assistant_msg, vault, editor_user,
            item_id=str(item.id),
            title="New Title",
        )
        assert result["status"] == "pending"
        action = PendingAction.objects.get(pk=result["pending_action_id"])
        assert action.payload["title"] == "New Title"

    def test_create_relation_pending(self, conversation, assistant_msg, vault, editor_user, item_type):
        a = ItemFactory(item_type=item_type, title="A", created_by=editor_user)
        b = ItemFactory(item_type=item_type, title="B", created_by=editor_user)
        result = create_relation(
            conversation, assistant_msg, vault, editor_user,
            relation_type_name="traces_to",
            source_id=str(a.id),
            target_id=str(b.id),
        )
        assert result["status"] == "pending"
