"""ElevenLabs TTS provider."""

import logging
from typing import AsyncIterator

from backend.providers.base import AudioFrame, TTSConfig, TTSProvider

logger = logging.getLogger(__name__)


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS provider using livekit-plugins-elevenlabs."""

    name = "elevenlabs"

    def __init__(self, api_key: str = "", default_voice: str = ""):
        self._api_key = api_key
        self._default_voice = default_voice

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        config: TTSConfig,
    ) -> AsyncIterator[AudioFrame]:
        """Stream text to audio using ElevenLabs API.

        For standalone usage outside LiveKit pipeline.
        """
        # ElevenLabs streaming is complex outside LiveKit.
        # Collect text and synthesize in chunks.
        import httpx

        buffer = ""
        async for chunk in text_stream:
            buffer += chunk
            # Synthesize on sentence boundaries
            if buffer and buffer[-1] in ".!?。！？\n":
                async for frame in self._synthesize_chunk(buffer, config):
                    yield frame
                buffer = ""

        if buffer.strip():
            async for frame in self._synthesize_chunk(buffer, config):
                yield frame

    async def _synthesize_chunk(
        self, text: str, config: TTSConfig
    ) -> AsyncIterator[AudioFrame]:
        """Synthesize a single text chunk."""
        import httpx

        voice = config.voice or self._default_voice
        model = config.model or "eleven_multilingual_v2"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream",
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
                timeout=30.0,
            )
            response.raise_for_status()

            yield AudioFrame(
                data=response.content,
                sample_rate=config.sample_rate,
                num_channels=1,
            )

    def create_livekit_plugin(self, config: TTSConfig):
        """Create a LiveKit-native TTS plugin for VoicePipelineAgent."""
        from livekit.plugins import elevenlabs

        return elevenlabs.TTS(
            voice=config.voice or self._default_voice,
            model_id=config.model or "eleven_multilingual_v2",
            api_key=self._api_key or None,
        )
