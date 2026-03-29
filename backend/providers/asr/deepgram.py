"""Deepgram ASR provider - wraps livekit-plugins-deepgram for our unified interface."""

import logging
from typing import AsyncIterator

from backend.providers.base import (
    ASRConfig,
    ASREvent,
    ASREventType,
    ASRProvider,
    ASRStream,
    AudioFrame,
)

logger = logging.getLogger(__name__)


class DeepgramASRStream(ASRStream):
    """Wraps Deepgram's streaming recognition into unified ASR events."""

    def __init__(self, stt_stream):
        self._stream = stt_stream
        self._started = False

    async def push_frame(self, frame: AudioFrame) -> None:
        # In LiveKit Agents, audio is pushed automatically via the pipeline.
        # This method is for standalone usage outside LiveKit.
        pass

    def __aiter__(self) -> AsyncIterator[ASREvent]:
        return self._iter_events()

    async def _iter_events(self) -> AsyncIterator[ASREvent]:
        async for event in self._stream:
            if not self._started:
                self._started = True
                yield ASREvent(type=ASREventType.START)

            if event.is_final:
                yield ASREvent(
                    type=ASREventType.END,
                    text=event.alternatives[0].text if event.alternatives else "",
                    confidence=event.alternatives[0].confidence if event.alternatives else 0.0,
                    is_final=True,
                    language=event.alternatives[0].language if event.alternatives else "",
                )
                self._started = False
            else:
                yield ASREvent(
                    type=ASREventType.CHANGE,
                    text=event.alternatives[0].text if event.alternatives else "",
                    confidence=event.alternatives[0].confidence if event.alternatives else 0.0,
                    is_final=False,
                )

    async def close(self) -> None:
        await self._stream.aclose()


class DeepgramASR(ASRProvider):
    """Deepgram ASR provider using livekit-plugins-deepgram."""

    name = "deepgram"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    async def create_stream(self, config: ASRConfig) -> ASRStream:
        from livekit.plugins import deepgram

        stt = deepgram.STT(
            language=config.language if config.language != "auto" else "zh",
            model=config.model or "nova-2",
            api_key=self._api_key or None,
        )
        stream = stt.stream()
        return DeepgramASRStream(stream)

    def create_livekit_plugin(self, config: ASRConfig):
        """Create a LiveKit-native STT plugin for use in VoicePipelineAgent."""
        from livekit.plugins import deepgram

        return deepgram.STT(
            language=config.language if config.language != "auto" else "zh",
            model=config.model or "nova-2",
            api_key=self._api_key or None,
        )
