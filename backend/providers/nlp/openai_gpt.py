"""OpenAI GPT NLP provider."""

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


class OpenAINLP(NLPProvider):
    """OpenAI GPT NLP provider using livekit-plugins-openai."""

    name = "openai"

    def __init__(self, api_key: str = "", default_model: str = "gpt-4o"):
        self._api_key = api_key
        self._default_model = default_model

    async def chat_stream(
        self,
        messages: list[NLPMessage],
        tools: list[ToolDefinition] | None,
        config: NLPConfig,
    ) -> AsyncIterator[NLPChunk]:
        """Streaming chat using the OpenAI SDK directly."""
        import openai

        client = openai.AsyncOpenAI(api_key=self._api_key or None)

        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        api_tools = None
        if tools:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        kwargs = {
            "model": config.model or self._default_model,
            "messages": api_messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        stream = await client.chat.completions.create(**kwargs)

        current_tool_calls: dict[int, dict] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.content:
                yield NLPChunk(type=NLPChunkType.TEXT, text=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name or "" if tc.function else "",
                            "args": "",
                        }
                    if tc.id:
                        current_tool_calls[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        current_tool_calls[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        current_tool_calls[idx]["args"] += tc.function.arguments

                    yield NLPChunk(
                        type=NLPChunkType.TOOL_CALL,
                        tool_call_id=current_tool_calls[idx]["id"],
                        tool_name=current_tool_calls[idx]["name"],
                        tool_args=current_tool_calls[idx]["args"],
                    )

            if chunk.choices[0].finish_reason == "tool_calls":
                for tc_data in current_tool_calls.values():
                    yield NLPChunk(
                        type=NLPChunkType.TOOL_CALL_DONE,
                        tool_call_id=tc_data["id"],
                        tool_name=tc_data["name"],
                        tool_args=tc_data["args"],
                    )

            if chunk.choices[0].finish_reason in ("stop", "tool_calls"):
                yield NLPChunk(type=NLPChunkType.DONE)

    def create_livekit_plugin(self, config: NLPConfig):
        """Create a LiveKit-native LLM plugin for VoicePipelineAgent."""
        from livekit.plugins import openai

        return openai.LLM(
            model=config.model or self._default_model,
            temperature=config.temperature,
            api_key=self._api_key or None,
        )
