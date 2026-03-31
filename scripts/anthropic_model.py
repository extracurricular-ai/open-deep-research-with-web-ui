"""
Anthropic Model adapter for smolagents.

smolagents has no built-in Anthropic support. This adapter implements
the smolagents Model interface using the Anthropic SDK, so agents in
run.py can use Claude models.
"""

import os
import time
from typing import Any

from anthropic import Anthropic, APIConnectionError, APITimeoutError, RateLimitError
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
    MessageRole,
    Model,
    TokenUsage,
)


class AnthropicModel(Model):
    """smolagents-compatible model that calls the Anthropic Messages API."""

    def __init__(
        self,
        model_id: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        max_tokens: int = 4096,
        custom_role_conversions: dict[str, str] | None = None,
        max_retries: int = 3,
        **kwargs,
    ):
        super().__init__(
            model_id=model_id,
            custom_role_conversions=custom_role_conversions,
            **kwargs,
        )
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    def generate(
        self,
        messages: list[ChatMessage],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list | None = None,
        **kwargs,
    ) -> ChatMessage:
        """Call Anthropic Messages API and return a ChatMessage."""
        # Separate system from conversation messages
        system_text = None
        conv_messages: list[dict[str, Any]] = []

        role_map = self.custom_role_conversions or {}

        for msg in messages:
            role = (
                msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role)
            )
            role = role_map.get(role, role)

            if role == "system":
                system_text = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                continue

            # Anthropic only accepts "user" and "assistant"
            if role not in ("user", "assistant"):
                role = "user"

            content = (
                msg.content if isinstance(msg.content, str) else str(msg.content or "")
            )
            conv_messages.append({"role": role, "content": content})

        # Build API kwargs
        api_kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": conv_messages,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
        }
        if system_text:
            api_kwargs["system"] = system_text
        if stop_sequences:
            api_kwargs["stop_sequences"] = stop_sequences

        # Tool use
        if tools_to_call_from:
            api_kwargs["tools"] = self._convert_tools(tools_to_call_from)

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(**api_kwargs)
                break
            except (APIConnectionError, APITimeoutError):
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # 1s, 2s, 4s
                    time.sleep(wait_time)
                    continue
                raise
            except RateLimitError:
                if attempt < self.max_retries - 1:
                    wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s
                    time.sleep(wait_time)
                    continue
                raise

        # Parse response
        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ChatMessageToolCall(
                        id=block.id,
                        type="function",
                        function=ChatMessageToolCallFunction(
                            name=block.name,
                            arguments=block.input,
                        ),
                    )
                )

        token_usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=content_text or None,
            tool_calls=tool_calls if tool_calls else None,
            raw=response,
            token_usage=token_usage,
        )

    @staticmethod
    def _convert_tools(tools: list) -> list[dict]:
        """Convert smolagents Tool objects to Anthropic tool format."""
        anthropic_tools = []
        for tool in tools:
            properties = {}
            required = []
            for param_name, param_info in (tool.inputs or {}).items():
                properties[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
                if not param_info.get("optional", False):
                    required.append(param_name)

            anthropic_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            )
        return anthropic_tools
