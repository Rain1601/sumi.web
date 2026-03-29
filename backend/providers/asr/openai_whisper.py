"""OpenAI Whisper ASR provider."""

import logging

from backend.providers.base import ASRConfig, ASRProvider, ASRStream

logger = logging.getLogger(__name__)


class OpenAIWhisperASR(ASRProvider):
    """OpenAI Whisper ASR via livekit-plugins-openai."""

    name = "openai"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    async def create_stream(self, config: ASRConfig) -> ASRStream:
        # Whisper is not a streaming ASR - it processes complete utterances.
        # In LiveKit, the Silero VAD segments speech, then Whisper transcribes each segment.
        raise NotImplementedError(
            "OpenAI Whisper works through LiveKit's VoicePipelineAgent VAD integration. "
            "Use create_livekit_plugin() instead."
        )

    def create_livekit_plugin(self, config: ASRConfig):
        """Create a LiveKit-native STT plugin for VoicePipelineAgent."""
        from livekit.plugins import openai

        return openai.STT(
            language=config.language if config.language != "auto" else "zh",
            model=config.model or "whisper-1",
            api_key=self._api_key or None,
        )
