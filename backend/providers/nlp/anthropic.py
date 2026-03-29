"""Anthropic Claude NLP provider."""

import logging
from typing import AsyncIterator

from backend.providers.base import (
    NLPChunk,
    NLPChunkType,
    NLPConfig,
    NLPMessage,
    NLPProvider,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class AnthropicNLP(NLPProvider):
    """Anthropic Claude NLP provider using livekit-plugins-anthropic."""

    name = "anthropic"

    def __init__(self, api_key: str = "", default_model: str = "claude-sonnet-4-20250514"):
        self._api_key = api_key
        self._default_model = default_model

    async def chat_stream(
        self,
        messages: list[NLPMessage],
        tools: list[ToolDefinition] | None,
        config: NLPConfig,
    ) -> AsyncIterator[NLPChunk]:
        """Streaming chat using the Anthropic SDK directly (for standalone usage)."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self._api_key or None)

        # Convert messages to Anthropic format
        system_msg = None
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        # Convert tools
        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in tools
            ]

        kwargs = {
            "model": config.model or self._default_model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "messages": api_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if api_tools:
            kwargs["tools"] = api_tools

        async with client.messages.stream(**kwargs) as stream:
            current_tool_id = ""
            current_tool_name = ""
            accumulated_args = ""

            async for event in stream:
                if event.type == "content_block_start":
                    if hasattr(event.content_block, "text"):
                        pass  # text block start
                    elif hasattr(event.content_block, "name"):
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        accumulated_args = ""
                        yield NLPChunk(
                            type=NLPChunkType.TOOL_CALL,
                            tool_call_id=current_tool_id,
                            tool_name=current_tool_name,
                        )

                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield NLPChunk(
                            type=NLPChunkType.TEXT,
                            text=event.delta.text,
                        )
                    elif hasattr(event.delta, "partial_json"):
                        accumulated_args += event.delta.partial_json
                        yield NLPChunk(
                            type=NLPChunkType.TOOL_CALL,
                            tool_call_id=current_tool_id,
                            tool_name=current_tool_name,
                            tool_args=accumulated_args,
                        )

                elif event.type == "content_block_stop":
                    if current_tool_name:
                        yield NLPChunk(
                            type=NLPChunkType.TOOL_CALL_DONE,
                            tool_call_id=current_tool_id,
                            tool_name=current_tool_name,
                            tool_args=accumulated_args,
                        )
                        current_tool_id = ""
                        current_tool_name = ""

                elif event.type == "message_stop":
                    yield NLPChunk(type=NLPChunkType.DONE)

    def create_livekit_plugin(self, config: NLPConfig):
        """Create a LiveKit-native LLM plugin for VoicePipelineAgent."""
        from livekit.plugins import anthropic

        return anthropic.LLM(
            model=config.model or self._default_model,
            temperature=config.temperature,
            api_key=self._api_key or None,
        )
