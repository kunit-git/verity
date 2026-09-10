"""Agent views: conversation CRUD, SSE chat, pending action accept/reject."""

from __future__ import annotations

import json
import logging

from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import SiteSettings
from apps.accounts.permissions import IsSiteAdmin, ReadOnlyOrEditor
from apps.items.models import Item, ItemType
from apps.relations.models import RelationType
from apps.vaults.mixins import VaultScopedMixin
from apps.vaults.permissions import HasVaultAccess, VaultNotLocked

from .models import Conversation, Message, PendingAction
from .providers import get_provider
from .serializers import (
    ChatInputSerializer,
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    PendingActionSerializer,
)
from .system_prompt import build_system_prompt
from .tools import READ_TOOLS, WRITE_TOOLS, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)


class AgentStatusView(APIView):
    """Returns whether AI is configured and enabled."""

    def get(self, request):
        settings = SiteSettings.get()
        return Response({
            "ai_enabled": settings.ai_enabled and bool(settings.ai_api_key),
        })


class AgentModelsView(APIView):
    """Fetch available models from the provider. Site admin only.

    Accepts an optional POST body to override saved credentials,
    so admins can test new settings before saving them.
    """

    permission_classes = [IsSiteAdmin]

    def post(self, request):
        site = SiteSettings.get()

        provider_type = request.data.get("ai_provider_type") or site.ai_provider_type
        api_url = request.data.get("ai_api_url") or site.ai_api_url or None
        api_key = request.data.get("ai_api_key") or site.ai_api_key

        if not provider_type:
            return Response(
                {"detail": "No provider type configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not api_key:
            return Response(
                {"detail": "No API key configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            models = _fetch_models(provider_type, api_key, api_url)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"models": models})


def _fetch_models(provider_type: str, api_key: str, base_url: str | None) -> list[str]:
    if provider_type == SiteSettings.AIProviderType.ANTHROPIC:
        from anthropic import Anthropic
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = Anthropic(**kwargs)
        resp = client.models.list(limit=100)
        return sorted([m.id for m in resp.data])
    else:
        from openai import OpenAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        resp = client.models.list()
        ids = sorted([m.id for m in resp.data])
        return ids


class ConversationListCreateView(VaultScopedMixin, generics.ListCreateAPIView):
    permission_classes = [HasVaultAccess]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ConversationCreateSerializer
        return ConversationListSerializer

    def get_queryset(self):
        return Conversation.objects.filter(
            user=self.request.user,
            vault=self.current_vault,
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["user"] = self.request.user
        ctx["vault"] = self.current_vault
        return ctx


class ConversationDetailView(VaultScopedMixin, generics.RetrieveDestroyAPIView):
    permission_classes = [HasVaultAccess]
    serializer_class = ConversationDetailSerializer

    def get_queryset(self):
        return Conversation.objects.filter(
            user=self.request.user,
            vault=self.current_vault,
        )


class ChatView(VaultScopedMixin, APIView):
    """Send a message and receive an SSE-streamed response."""

    permission_classes = [HasVaultAccess]

    def post(self, request, pk):
        conversation = generics.get_object_or_404(
            Conversation,
            pk=pk, user=request.user, vault=self.current_vault,
        )
        serializer = ChatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_message_text = serializer.validated_data["message"]

        # Save user message
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=user_message_text,
        )

        vault = self.current_vault
        user = request.user

        # Build context
        context_item = conversation.context_item
        if context_item:
            try:
                context_item = Item.objects.select_related("item_type").get(pk=context_item.pk)
            except Item.DoesNotExist:
                context_item = None

        system_prompt = build_system_prompt(vault, user, context_item)

        # Build message history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation.messages.all():
            entry = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_name:
                entry["name"] = msg.tool_name
            messages.append(entry)

        try:
            provider = get_provider()
        except RuntimeError as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        model = SiteSettings.get().ai_model

        def event_stream():
            """Generator that streams SSE events."""
            try:
                yield from _run_agent_loop(
                    provider, model, messages, conversation, vault, user
                )
            except Exception as e:
                logger.exception("Agent loop error")
                yield _sse("error", {"detail": str(e)})
            yield _sse("done", {})

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


def _run_agent_loop(provider, model, messages, conversation, vault, user):
    """Run the agent loop: call LLM, handle tool calls, repeat."""
    max_iterations = 10
    for _ in range(max_iterations):
        events = provider.stream_chat(messages, TOOL_DEFINITIONS, model)

        assistant_content = ""
        all_tool_calls = []

        for event in events:
            if event.error:
                yield _sse("error", {"detail": event.error})
                return
            if event.token:
                assistant_content += event.token
                yield _sse("token", {"content": event.token})
            if event.tool_calls:
                all_tool_calls.extend(event.tool_calls)

        if not all_tool_calls:
            # No tool calls — save assistant message and finish
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.ASSISTANT,
                content=assistant_content,
            )
            return

        # Save assistant message with tool calls
        serialized_tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in all_tool_calls
        ]
        assistant_msg = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=assistant_content,
            tool_calls=serialized_tool_calls,
        )
        messages.append({
            "role": "assistant",
            "content": assistant_content,
            "tool_calls": serialized_tool_calls,
        })

        # Process tool calls
        has_write_tool = False
        for tc in all_tool_calls:
            result = _execute_tool(tc, conversation, assistant_msg, vault, user)
            if tc.name in WRITE_TOOLS:
                has_write_tool = True
                # Emit pending action SSE event
                if "pending_action_id" in result:
                    action = PendingAction.objects.get(pk=result["pending_action_id"])
                    yield _sse("pending_action", PendingActionSerializer(action).data)

            result_str = json.dumps(result)
            Message.objects.create(
                conversation=conversation,
                role=Message.Role.TOOL,
                content=result_str,
                tool_call_id=tc.id,
                tool_name=tc.name,
            )
            messages.append({
                "role": "tool",
                "content": result_str,
                "tool_call_id": tc.id,
                "name": tc.name,
            })

        # If there were write tools, let the LLM respond one more time
        # to acknowledge the pending actions, then stop.
        if has_write_tool:
            events = provider.stream_chat(messages, TOOL_DEFINITIONS, model)
            final_content = ""
            for event in events:
                if event.token:
                    final_content += event.token
                    yield _sse("token", {"content": event.token})
            if final_content:
                Message.objects.create(
                    conversation=conversation,
                    role=Message.Role.ASSISTANT,
                    content=final_content,
                )
            return
        # Otherwise loop — the LLM may call more read tools


def _execute_tool(tool_call, conversation, assistant_msg, vault, user):
    """Execute a single tool call and return the result dict."""
    name = tool_call.name
    args = tool_call.arguments

    if name in READ_TOOLS:
        try:
            return READ_TOOLS[name](vault, user, **args)
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return {"error": str(e)}
    elif name in WRITE_TOOLS:
        try:
            return WRITE_TOOLS[name](conversation, assistant_msg, vault, user, **args)
        except Exception as e:
            logger.exception(f"Tool {name} failed")
            return {"error": str(e)}
    else:
        return {"error": f"Unknown tool: {name}"}


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class PendingActionAcceptView(VaultScopedMixin, APIView):
    """Execute a pending action."""

    permission_classes = [HasVaultAccess, ReadOnlyOrEditor, VaultNotLocked]

    @transaction.atomic
    def post(self, request, pk):
        action = generics.get_object_or_404(
            PendingAction.objects.select_for_update().select_related("conversation"),
            pk=pk, conversation__vault=self.current_vault,
            conversation__user=request.user,
        )
        if action.status != PendingAction.Status.PENDING:
            return Response(
                {"detail": f"Action is already {action.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                result = _execute_pending_action(action, request)
            action.status = PendingAction.Status.EXECUTED
            action.result = result
        except Exception as e:
            action.status = PendingAction.Status.FAILED
            action.result = {"error": str(e)}

        action.resolved_at = timezone.now()
        action.save()
        return Response(PendingActionSerializer(action).data)


class PendingActionRejectView(VaultScopedMixin, APIView):
    """Reject a pending action."""

    permission_classes = [HasVaultAccess]

    @transaction.atomic
    def post(self, request, pk):
        action = generics.get_object_or_404(
            PendingAction.objects.select_for_update().select_related("conversation"),
            pk=pk,
            conversation__vault=self.current_vault,
            conversation__user=request.user,
        )
        if action.status != PendingAction.Status.PENDING:
            return Response(
                {"detail": f"Action is already {action.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action.status = PendingAction.Status.REJECTED
        action.resolved_at = timezone.now()
        action.save()
        return Response(PendingActionSerializer(action).data)


def _execute_pending_action(action, request):
    """Execute a pending action using the same serializers as the regular API."""
    from apps.items.serializers import ItemSerializer
    from apps.relations.serializers import ItemRelationSerializer

    payload = action.payload
    vault = action.conversation.vault

    if action.action_type == PendingAction.ActionType.CREATE_ITEM:
        item_type = ItemType.objects.get(vault=vault, slug=payload["item_type_slug"])
        data = {
            "item_type": str(item_type.id),
            "title": payload["title"],
            "description": payload.get("description", ""),
            "status": payload.get("status", "draft"),
            "custom_fields": payload.get("custom_fields", {}),
        }
        serializer = ItemSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return {"item_id": str(item.id), "title": item.title}

    elif action.action_type == PendingAction.ActionType.UPDATE_ITEM:
        item = Item.objects.get(pk=payload["item_id"], item_type__vault=vault)
        data = {}
        if "title" in payload:
            data["title"] = payload["title"]
        if "description" in payload:
            data["description"] = payload["description"]
        if "status" in payload:
            data["status"] = payload["status"]
        if "custom_fields" in payload:
            data["custom_fields"] = payload["custom_fields"]
        serializer = ItemSerializer(item, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return {"item_id": str(item.id), "title": item.title, "version": item.current_version}

    elif action.action_type == PendingAction.ActionType.CREATE_RELATION:
        rel_type = RelationType.objects.get(vault=vault, name=payload["relation_type_name"])
        data = {
            "relation_type": str(rel_type.id),
            "source": payload["source_id"],
            "target": payload["target_id"],
        }
        serializer = ItemRelationSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        relation = serializer.save()
        return {"relation_id": str(relation.id)}

    else:
        raise ValueError(f"Unknown action type: {action.action_type}")
