"""Instrumented LLM wrapper for structured tracing (TTFB/TTF10T per invocation)."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from livekit.agents import llm, NOT_GIVEN

if TYPE_CHECKING:
    from backend.tracing.trace_log import TraceContext

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.5 chars per token for CJK-heavy, ~4 for English."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ratio = 1.5 if cjk > len(text) * 0.3 else 4
    return max(1, int(len(text) / ratio))


class InstrumentedLLMStream:
    """Proxy around an ``LLMStream`` that intercepts token iteration to
    record first-token (TTFB) and 10th-token (TTF10T) timing via the
    ``TraceContext``.

    Only counts chunks that carry actual content text as "tokens".
    Supports per-invocation tracking for multi-round tool calling.
    """

    def __init__(self, inner: llm.LLMStream, ctx: TraceContext, model: str = "") -> None:
        self._inner = inner
        self._ctx = ctx
        self._model = model
        self._content_token_count = 0
        self._first_reported = False
        self._tenth_reported = False

    # -- async-iterator protocol ------------------------------------------

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._inner.__anext__()

        # Only count chunks with actual content text
        has_content = False
        if hasattr(chunk, "choices"):
            for choice in chunk.choices:
                delta = getattr(choice, "delta", None)
                if delta and getattr(delta, "content", None):
                    has_content = True
                    break
        elif hasattr(chunk, "delta") and getattr(chunk.delta, "content", None):
            has_content = True
        elif hasattr(chunk, "content") and chunk.content:
            has_content = True

        if has_content:
            self._content_token_count += 1
            self._ctx.nlp_content_tokens += 1

            now = time.time()

            if not self._first_reported:
                self._first_reported = True
                self._ctx.nlp_ttfb = now
                ttfb_ms = (now - self._ctx.nlp_start) * 1000 if self._ctx.nlp_start else 0
                self._ctx.emit("nlp.first_token", result={
                    "ttfb_ms": round(ttfb_ms, 1),
                    "model": self._model,
                    "sentence_id": self._ctx.sentence_id,
                })

            if self._content_token_count == 10 and not self._tenth_reported:
                self._tenth_reported = True
                self._ctx.nlp_ttf10t = now
                ttf10t_ms = (now - self._ctx.nlp_start) * 1000 if self._ctx.nlp_start else 0
                self._ctx.emit("nlp.ttf10t", result={
                    "ttf10t_ms": round(ttf10t_ms, 1),
                    "model": self._model,
                    "sentence_id": self._ctx.sentence_id,
                })

        self._ctx.nlp_total_chunks += 1
        return chunk

    # -- async-context-manager protocol ------------------------------------

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, exc_tb):
        return await self._inner.__aexit__(exc_type, exc, exc_tb)

    # -- transparent proxy for everything else -----------------------------

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class InstrumentedLLM(llm.LLM):
    """Wraps any ``llm.LLM`` to intercept the ``chat()`` return value and
    wrap the resulting ``LLMStream`` with timing instrumentation.

    Records chat_ctx size (message count + estimated tokens) and emits
    structured TraceLog events for each LLM invocation.
    """

    def __init__(self, inner: llm.LLM, ctx: TraceContext) -> None:
        # Don't call super().__init__() — we proxy, not inherit behaviour.
        self._inner = inner
        self._ctx = ctx
        self._label = inner._label

    # -- proxy properties --------------------------------------------------

    @property
    def model(self) -> str:
        return self._inner.model

    @property
    def provider(self) -> str:
        return self._inner.provider

    # -- core interface: chat ----------------------------------------------

    def chat(
        self,
        *,
        chat_ctx,
        tools=None,
        conn_options=None,
        parallel_tool_calls=NOT_GIVEN,
        tool_choice=NOT_GIVEN,
        extra_kwargs=NOT_GIVEN,
        **kwargs,
    ) -> InstrumentedLLMStream:
        # Record chat_ctx size before the call
        msg_count = len(chat_ctx.items) if hasattr(chat_ctx, "items") else 0
        token_est = 0
        if hasattr(chat_ctx, "items"):
            for item in chat_ctx.items:
                for content in getattr(item, "content", []):
                    if hasattr(content, "text"):
                        token_est += _estimate_tokens(content.text or "")

        self._ctx.ctx_messages = msg_count
        self._ctx.ctx_tokens_est = token_est
        self._ctx.nlp_start = time.time()

        # Emit nlp.start with context size info
        tool_names = []
        if tools:
            tool_names = [getattr(t, "name", str(t)) for t in tools]

        self._ctx.emit("nlp.start", request={
            "model": self._inner.model,
            "ctx_messages": msg_count,
            "ctx_tokens_est": token_est,
            "tools": tool_names,
            "invocation": self._ctx.nlp_invocation,
        })

        stream = self._inner.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
            **kwargs,
        )
        return InstrumentedLLMStream(stream, self._ctx, model=self._inner.model)

    # -- lifecycle ---------------------------------------------------------

    async def aclose(self) -> None:
        await self._inner.aclose()

    def prewarm(self) -> None:
        self._inner.prewarm()

    # -- event emitter proxy -----------------------------------------------

    def on(self, event, callback=None):
        return self._inner.on(event, callback)

    def once(self, event, callback=None):
        return self._inner.once(event, callback)

    def off(self, event, callback):
        return self._inner.off(event, callback)

    def emit(self, event, *args):
        return self._inner.emit(event, *args)
