"""OpenAI TTS provider."""

import logging
from typing import AsyncIterator

from backend.providers.base import AudioFrame, TTSConfig, TTSProvider

logger = logging.getLogger(__name__)


class OpenAITTS(TTSProvider):
    """OpenAI TTS provider using livekit-plugins-openai."""

    name = "openai"

    def __init__(self, api_key: str = "", default_voice: str = "alloy"):
        self._api_key = api_key
        self._default_voice = default_voice

    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        config: TTSConfig,
    ) -> AsyncIterator[AudioFrame]:
        """Stream text to audio via OpenAI TTS API."""
        import openai

        client = openai.AsyncOpenAI(api_key=self._api_key or None)

        buffer = ""
        async for chunk in text_stream:
            buffer += chunk
            if buffer and buffer[-1] in ".!?。！？\n":
                response = await client.audio.speech.create(
                    model=config.model or "tts-1",
                    voice=config.voice or self._default_voice,
                    input=buffer,
                    speed=config.speed,
                )
                yield AudioFrame(
                    data=response.content,
                    sample_rate=config.sample_rate,
                    num_channels=1,
                )
                buffer = ""

        if buffer.strip():
            response = await client.audio.speech.create(
                model=config.model or "tts-1",
                voice=config.voice or self._default_voice,
                input=buffer,
                speed=config.speed,
            )
            yield AudioFrame(
                data=response.content,
                sample_rate=config.sample_rate,
                num_channels=1,
            )

    def create_livekit_plugin(self, config: TTSConfig):
        """Create a LiveKit-native TTS plugin for VoicePipelineAgent."""
        from livekit.plugins import openai

        return openai.TTS(
            voice=config.voice or self._default_voice,
            model=config.model or "tts-1",
            api_key=self._api_key or None,
        )
