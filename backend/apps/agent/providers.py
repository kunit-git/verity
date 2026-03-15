"""LLM provider abstraction supporting OpenAI and Anthropic APIs."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from apps.accounts.models import SiteSettings

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class StreamEvent:
    token: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    done: bool = False
    error: str = ""


class LLMProvider(ABC):
    @abstractmethod
    def stream_chat(
        self, messages: list[dict], tools: list[dict], model: str
    ) -> list[StreamEvent]:
        """Send messages and return a list of stream events."""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str | None = None):
        from openai import OpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def stream_chat(
        self, messages: list[dict], tools: list[dict], model: str
    ) -> list[StreamEvent]:
        kwargs = {"model": model, "messages": messages, "stream": True}
        if tools:
            kwargs["tools"] = tools
        events = []
        tool_call_parts: dict[int, dict] = {}
        try:
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                if delta.content:
                    events.append(StreamEvent(token=delta.content))
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_call_parts:
                            tool_call_parts[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            tool_call_parts[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_call_parts[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_call_parts[idx]["arguments"] += tc.function.arguments
                if chunk.choices[0].finish_reason:
                    break
        except Exception as e:
            logger.exception("OpenAI streaming error")
            events.append(StreamEvent(error=str(e)))
            return events

        # Emit accumulated tool calls
        if tool_call_parts:
            tcs = []
            for _idx, parts in sorted(tool_call_parts.items()):
                try:
                    args = json.loads(parts["arguments"]) if parts["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                tcs.append(ToolCall(id=parts["id"], name=parts["name"], arguments=args))
            events.append(StreamEvent(tool_calls=tcs))

        events.append(StreamEvent(done=True))
        return events


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str | None = None):
        from anthropic import Anthropic

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Separate system message from conversation messages for Anthropic API."""
        system = ""
        conv_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            elif msg["role"] == "tool":
                conv_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": msg["content"],
                        }
                    ],
                })
            elif msg["role"] == "assistant" and msg.get("tool_calls"):
                content = []
                if msg.get("content"):
                    content.append({"type": "text", "text": msg["content"]})
                for tc in msg["tool_calls"]:
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], str)
                        else tc["function"]["arguments"],
                    })
                conv_messages.append({"role": "assistant", "content": content})
            else:
                conv_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
        return system, conv_messages

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-format tool defs to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    def stream_chat(
        self, messages: list[dict], tools: list[dict], model: str
    ) -> list[StreamEvent]:
        system, conv_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools) if tools else []

        events = []
        kwargs = {
            "model": model,
            "max_tokens": 4096,
            "messages": conv_messages,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        try:
            with self.client.messages.stream(**kwargs) as stream:
                current_tool_id = None
                current_tool_name = None
                current_tool_input = ""

                for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, "type"):
                            if event.content_block.type == "tool_use":
                                current_tool_id = event.content_block.id
                                current_tool_name = event.content_block.name
                                current_tool_input = ""
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            events.append(StreamEvent(token=event.delta.text))
                        elif hasattr(event.delta, "partial_json"):
                            current_tool_input += event.delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool_id:
                            try:
                                args = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                args = {}
                            events.append(StreamEvent(tool_calls=[
                                ToolCall(
                                    id=current_tool_id,
                                    name=current_tool_name,
                                    arguments=args,
                                )
                            ]))
                            current_tool_id = None
                            current_tool_name = None
                            current_tool_input = ""
        except Exception as e:
            logger.exception("Anthropic streaming error")
            events.append(StreamEvent(error=str(e)))
            return events

        events.append(StreamEvent(done=True))
        return events


def get_provider() -> LLMProvider:
    """Factory: create the appropriate provider from SiteSettings."""
    site = SiteSettings.get()
    if not site.ai_enabled or not site.ai_api_key:
        raise RuntimeError("AI is not configured.")

    if site.ai_provider_type == SiteSettings.AIProviderType.ANTHROPIC:
        return AnthropicProvider(
            api_key=site.ai_api_key,
            base_url=site.ai_api_url or None,
        )
    else:
        return OpenAIProvider(
            api_key=site.ai_api_key,
            base_url=site.ai_api_url or None,
        )
