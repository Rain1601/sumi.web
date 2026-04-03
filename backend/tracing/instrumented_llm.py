"""Instrumented LLM wrapper for TTFB/TTF10T tracing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from livekit.agents import llm, NOT_GIVEN

if TYPE_CHECKING:
    from backend.tracing.session_tracer import SessionTracer

logger = logging.getLogger(__name__)


class InstrumentedLLMStream:
    """Proxy around an ``LLMStream`` that intercepts token iteration to
    record first-token (TTFB) and 10th-token (TTF10T) timing via the
    ``SessionTracer``.

    Every attribute / method that is *not* overridden here is forwarded
    transparently to the inner stream so that ``AgentSession`` can use
    it exactly like a normal ``LLMStream``.
    """

    def __init__(self, inner: llm.LLMStream, tracer: SessionTracer) -> None:
        self._inner = inner
        self._tracer = tracer
        self._token_count = 0
        self._first_reported = False
        self._tenth_reported = False

    # -- async-iterator protocol ------------------------------------------

    def __aiter__(self):
        return self

    async def __anext__(self):
        chunk = await self._inner.__anext__()

        # Count every chunk that carries content as a "token"
        self._token_count += 1

        if not self._first_reported:
            self._first_reported = True
            self._tracer.record_nlp_first_token()

        if self._token_count == 10 and not self._tenth_reported:
            self._tenth_reported = True
            self._tracer.record_nlp_token()  # records TTF10T
        elif self._token_count > 10:
            self._tracer.record_nlp_token()  # just increments counter

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
    wrap the resulting ``LLMStream`` with timing instrumentation."""

    def __init__(self, inner: llm.LLM, tracer: SessionTracer) -> None:
        # Don't call super().__init__() — we proxy, not inherit behaviour.
        self._inner = inner
        self._tracer = tracer
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
        stream = self._inner.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
            **kwargs,
        )
        return InstrumentedLLMStream(stream, self._tracer)

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
