"""Instrumented TTS wrapper for first-audio-frame tracing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from livekit.agents import tts

if TYPE_CHECKING:
    from backend.tracing.session_tracer import SessionTracer

logger = logging.getLogger(__name__)


class InstrumentedSynthesizeStream:
    """Proxy around a ``SynthesizeStream`` that detects the first audio
    frame and reports it to the ``SessionTracer``."""

    def __init__(self, inner: tts.SynthesizeStream, tracer: SessionTracer) -> None:
        self._inner = inner
        self._tracer = tracer
        self._first_audio_reported = False

    # -- async-iterator protocol ------------------------------------------

    def __aiter__(self):
        return self

    async def __anext__(self) -> tts.SynthesizedAudio:
        audio = await self._inner.__anext__()

        if not self._first_audio_reported:
            self._first_audio_reported = True
            self._tracer.record_tts_first_audio()

        return audio

    # -- async-context-manager protocol ------------------------------------

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, exc_tb):
        return await self._inner.__aexit__(exc_type, exc, exc_tb)

    # -- transparent proxy for everything else -----------------------------

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class InstrumentedChunkedStream:
    """Proxy around a ``ChunkedStream`` that detects the first audio
    frame and reports it to the ``SessionTracer``."""

    def __init__(self, inner: tts.ChunkedStream, tracer: SessionTracer) -> None:
        self._inner = inner
        self._tracer = tracer
        self._first_audio_reported = False

    # -- async-iterator protocol ------------------------------------------

    def __aiter__(self):
        return self

    async def __anext__(self) -> tts.SynthesizedAudio:
        audio = await self._inner.__anext__()

        if not self._first_audio_reported:
            self._first_audio_reported = True
            self._tracer.record_tts_first_audio()

        return audio

    # -- async-context-manager protocol ------------------------------------

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, exc_tb):
        return await self._inner.__aexit__(exc_type, exc, exc_tb)

    # -- transparent proxy for everything else -----------------------------

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


class InstrumentedTTS(tts.TTS):
    """Wraps any ``tts.TTS`` to capture first audio frame timing via the
    ``SessionTracer``."""

    def __init__(self, inner: tts.TTS, tracer: SessionTracer) -> None:
        # Don't call super().__init__() — we proxy, not inherit behaviour.
        self._inner = inner
        self._tracer = tracer
        self._capabilities = inner._capabilities
        self._sample_rate = inner._sample_rate
        self._num_channels = inner._num_channels
        self._label = inner._label

    # -- core interface ----------------------------------------------------

    def synthesize(self, text: str, *, conn_options=None) -> InstrumentedChunkedStream:
        kwargs = {}
        if conn_options is not None:
            kwargs["conn_options"] = conn_options
        inner_stream = self._inner.synthesize(text, **kwargs)
        return InstrumentedChunkedStream(inner_stream, self._tracer)

    def stream(self, *, conn_options=None) -> InstrumentedSynthesizeStream:
        kwargs = {}
        if conn_options is not None:
            kwargs["conn_options"] = conn_options
        inner_stream = self._inner.stream(**kwargs)
        return InstrumentedSynthesizeStream(inner_stream, self._tracer)

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
