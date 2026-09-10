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
    def test_chat_on_other_users_conversation_returns_404(self, viewer_client, conversation):
        response = viewer_client.post(
            f"/api/v1/agent/conversations/{conversation.id}/chat/",
            {"message": "Hello"}, format="json",
        )
        assert response.status_code == 404
        assert not conversation.messages.exists()

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
    @pytest.mark.django_db(transaction=True)
    def test_concurrent_accept_executes_once(self, editor_user, pending_action):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.contrib.auth import get_user_model
        from django.db import close_old_connections
        from rest_framework.test import APIClient
        from apps.items.models import Item

        barrier = Barrier(2)

        def accept(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=editor_user.pk))
                barrier.wait(timeout=10)
                return client.post(
                    f"/api/v1/agent/pending-actions/{pending_action.pk}/accept/"
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(accept, range(2)))
        assert sorted(statuses) == [200, 400]
        assert Item.objects.filter(title=pending_action.payload["title"]).count() == 1

    @pytest.mark.parametrize("operation", ["accept", "reject"])
    def test_other_editor_cannot_resolve_action(self, viewer_client, viewer_user, pending_action, operation):
        from apps.vaults.models import VaultMembership

        VaultMembership.objects.filter(user=viewer_user).update(role="editor")
        response = viewer_client.post(
            f"/api/v1/agent/pending-actions/{pending_action.id}/{operation}/"
        )
        assert response.status_code == 404
        pending_action.refresh_from_db()
        assert pending_action.status == "pending"

    @pytest.mark.parametrize("operation", ["accept", "reject"])
    def test_missing_action_returns_404(self, editor_client, operation):
        from uuid import uuid4

        response = editor_client.post(f"/api/v1/agent/pending-actions/{uuid4()}/{operation}/")
        assert response.status_code == 404

    def test_failed_action_rolls_back_partial_writes(self, editor_client, pending_action, item_type, monkeypatch):
        from apps.agent import views
        from apps.items.models import Item

        def fail_after_write(action, request):
            ItemFactory(item_type=item_type, title="Should roll back")
            raise ValueError("Test failure after writing")

        monkeypatch.setattr(views, "_execute_pending_action", fail_after_write)
        response = editor_client.post(f"/api/v1/agent/pending-actions/{pending_action.id}/accept/")
        assert response.status_code == 200
        assert response.data["status"] == "failed"
        assert not Item.objects.filter(title="Should roll back").exists()

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
