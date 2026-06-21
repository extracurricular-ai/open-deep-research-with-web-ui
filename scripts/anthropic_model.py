"""
Anthropic Model adapter for smolagents.

smolagents has no built-in Anthropic support. This adapter implements
the smolagents Model interface using the Anthropic SDK, so agents in
run.py can use Claude models.
"""

import os
import sys
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
        enable_prompt_caching: bool = True,
        **kwargs,
    ):
        super().__init__(
            model_id=model_id,
            custom_role_conversions=custom_role_conversions,
            **kwargs,
        )
        # smolagents' base Model.__init__ does NOT store custom_role_conversions
        # (it lands in self.kwargs), but generate() below reads
        # self.custom_role_conversions — set it explicitly or every call AttributeErrors.
        self.custom_role_conversions = custom_role_conversions or {}
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        # Anthropic prompt caching is opt-in: without cache_control breakpoints
        # NOTHING is cached (unlike OpenAI/DeepSeek, which cache automatically).
        # When enabled we mark the (stable) system+tools prefix and the growing
        # conversation tail with `cache_control`, mirroring the recommended
        # prefix-cache layout. Cache reads cost ~0.1x; verify via the
        # [anthropic-cache] stderr line (cache_read_input_tokens).
        self.enable_prompt_caching = enable_prompt_caching
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

        # Prompt caching: mark the last non-empty conversation block so the whole
        # growing message prefix is cached turn-over-turn (incremental hits). The
        # 20-block lookback is fine — each agent step adds only a couple of blocks.
        if self.enable_prompt_caching and conv_messages:
            for m in reversed(conv_messages):
                if isinstance(m["content"], str) and m["content"].strip():
                    m["content"] = [
                        {
                            "type": "text",
                            "text": m["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                    break

        # Build API kwargs
        api_kwargs: dict[str, Any] = {
            "model": self.model_id,
            "messages": conv_messages,
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
        }
        if system_text:
            if self.enable_prompt_caching:
                # A breakpoint on the (stable) system block caches tools + system —
                # the highest-value, byte-stable prefix across the whole run.
                api_kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
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

        # Visibility into cache effectiveness — smolagents' TokenUsage has no field
        # for these, so surface them on stderr. cache_read_input_tokens > 0 across
        # turns confirms the prefix cache is hitting.
        if self.enable_prompt_caching:
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            cache_creation = (
                getattr(response.usage, "cache_creation_input_tokens", 0) or 0
            )
            print(
                f"[anthropic-cache] read={cache_read} creation={cache_creation} "
                f"input={response.usage.input_tokens} "
                f"output={response.usage.output_tokens}",
                file=sys.stderr,
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
