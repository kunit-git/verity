import pytest
from apps.agent.models import Conversation, Message, PendingAction
from conftest import ItemFactory, VaultFactory


@pytest.fixture
def conversation(vault, editor_user):
    return Conversation.objects.create(user=editor_user, vault=vault)


class TestAgentStatus:
    def test_status_unauthenticated(self, api_client):
        r = api_client.get("/api/v1/agent/status/")
        assert r.status_code == 401

    def test_status_default_disabled(self, editor_client):
        r = editor_client.get("/api/v1/agent/status/")
        assert r.status_code == 200
        assert r.data["ai_enabled"] is False


class TestConversationCRUD:
    def test_create_conversation(self, editor_client, vault):
        r = editor_client.post("/api/v1/agent/conversations/", {"title": "Test Chat"}, format="json")
        assert r.status_code == 201
        assert r.data["title"] == "Test Chat"

    def test_create_with_context_item(self, editor_client, vault, item_type, editor_user):
        item = ItemFactory(item_type=item_type, title="Context", created_by=editor_user)
        r = editor_client.post(
            "/api/v1/agent/conversations/",
            {"title": "With Context", "context_item": str(item.id)},
            format="json",
        )
        assert r.status_code == 201
        assert str(r.data["context_item"]) == str(item.id)

    def test_list_conversations(self, editor_client, conversation):
        r = editor_client.get("/api/v1/agent/conversations/")
        assert r.status_code == 200
        assert len(r.data["results"]) == 1

    def test_get_conversation_detail(self, editor_client, conversation):
        r = editor_client.get(f"/api/v1/agent/conversations/{conversation.id}/")
        assert r.status_code == 200
        assert r.data["id"] == str(conversation.id)
        assert "messages" in r.data

    def test_delete_conversation(self, editor_client, conversation):
        r = editor_client.delete(f"/api/v1/agent/conversations/{conversation.id}/")
        assert r.status_code == 204
        assert not Conversation.objects.filter(pk=conversation.id).exists()

    def test_viewer_can_create_conversation(self, viewer_client, vault):
        r = viewer_client.post("/api/v1/agent/conversations/", {"title": "Viewer Chat"}, format="json")
        assert r.status_code == 201

    def test_cannot_see_other_users_conversations(self, viewer_client, conversation):
        r = viewer_client.get("/api/v1/agent/conversations/")
        assert r.status_code == 200
        assert len(r.data["results"]) == 0


class TestPendingActionAcceptReject:
    @pytest.fixture
    def pending_action(self, conversation, item_type):
        msg = Message.objects.create(
            conversation=conversation, role="assistant", content="I'll create that."
        )
        return PendingAction.objects.create(
            conversation=conversation,
            message=msg,
            action_type="create_item",
            payload={
                "item_type_slug": item_type.slug,
                "title": "AI-Created Requirement",
                "description": "Created by the agent",
                "status": "draft",
                "custom_fields": {},
            },
        )

    def test_accept_creates_item(self, editor_client, pending_action):
        r = editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        assert r.status_code == 200
        assert r.data["status"] == "executed"
        assert "item_id" in r.data["result"]

    def test_reject_action(self, editor_client, pending_action):
        r = editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/reject/")
        # Editor is not the conversation owner (conversation belongs to editor_user,
        # but let's check it works when it IS the right user)
        assert r.status_code == 200
        assert r.data["status"] == "rejected"

    def test_cannot_accept_twice(self, editor_client, pending_action):
        editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        r = editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        assert r.status_code == 400

    def test_viewer_cannot_accept(self, viewer_client, pending_action):
        r = viewer_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        assert r.status_code == 403

    def test_accept_update_item(self, editor_client, conversation, item_type, editor_user):
        item = ItemFactory(item_type=item_type, title="Original", created_by=editor_user)
        msg = Message.objects.create(
            conversation=conversation, role="assistant", content="Updating..."
        )
        action = PendingAction.objects.create(
            conversation=conversation,
            message=msg,
            action_type="update_item",
            payload={
                "item_id": str(item.id),
                "title": "Updated by AI",
            },
        )
        r = editor_client.post(f"/api/v1/agent/pending-actions/{action.id}/accept/")
        assert r.status_code == 200
        assert r.data["status"] == "executed"
        item.refresh_from_db()
        assert item.title == "Updated by AI"
        assert item.current_version == 2

    def test_accept_create_relation(self, editor_client, conversation, item_type, trace_type, editor_user):
        a = ItemFactory(item_type=item_type, title="Source", created_by=editor_user)
        b = ItemFactory(item_type=item_type, title="Target", created_by=editor_user)
        msg = Message.objects.create(
            conversation=conversation, role="assistant", content="Linking..."
        )
        action = PendingAction.objects.create(
            conversation=conversation,
            message=msg,
            action_type="create_relation",
            payload={
                "relation_type_name": "traces_to",
                "source_id": str(a.id),
                "target_id": str(b.id),
            },
        )
        r = editor_client.post(f"/api/v1/agent/pending-actions/{action.id}/accept/")
        assert r.status_code == 200
        assert r.data["status"] == "executed"
        assert "relation_id" in r.data["result"]

    def test_locked_vault_blocks_accept(self, editor_client, pending_action, vault):
        vault.is_locked = True
        vault.save()
        r = editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        assert r.status_code == 403
        vault.is_locked = False
        vault.save()
