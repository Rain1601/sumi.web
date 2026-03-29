"""Provider registry for discovering and instantiating ASR/TTS/NLP providers."""

from typing import Type

from backend.providers.base import ASRProvider, NLPProvider, TTSProvider


class ProviderRegistry:
    """Singleton registry mapping provider names to classes."""

    def __init__(self):
        self._asr: dict[str, Type[ASRProvider]] = {}
        self._tts: dict[str, Type[TTSProvider]] = {}
        self._nlp: dict[str, Type[NLPProvider]] = {}
        self._instances: dict[str, ASRProvider | TTSProvider | NLPProvider] = {}

    def register_asr(self, name: str, cls: Type[ASRProvider]):
        self._asr[name] = cls

    def register_tts(self, name: str, cls: Type[TTSProvider]):
        self._tts[name] = cls

    def register_nlp(self, name: str, cls: Type[NLPProvider]):
        self._nlp[name] = cls

    def get_asr(self, name: str, **kwargs) -> ASRProvider:
        key = f"asr:{name}"
        if key not in self._instances:
            if name not in self._asr:
                raise ValueError(f"Unknown ASR provider: {name}. Available: {list(self._asr)}")
            self._instances[key] = self._asr[name](**kwargs)
        return self._instances[key]

    def get_tts(self, name: str, **kwargs) -> TTSProvider:
        key = f"tts:{name}"
        if key not in self._instances:
            if name not in self._tts:
                raise ValueError(f"Unknown TTS provider: {name}. Available: {list(self._tts)}")
            self._instances[key] = self._tts[name](**kwargs)
        return self._instances[key]

    def get_nlp(self, name: str, **kwargs) -> NLPProvider:
        key = f"nlp:{name}"
        if key not in self._instances:
            if name not in self._nlp:
                raise ValueError(f"Unknown NLP provider: {name}. Available: {list(self._nlp)}")
            self._instances[key] = self._nlp[name](**kwargs)
        return self._instances[key]

    def list_asr(self) -> list[str]:
        return list(self._asr.keys())

    def list_tts(self) -> list[str]:
        return list(self._tts.keys())

    def list_nlp(self) -> list[str]:
        return list(self._nlp.keys())


# Global registry instance
registry = ProviderRegistry()


def register_default_providers():
    """Register all built-in providers. Called at startup."""
    from backend.providers.asr.deepgram import DeepgramASR
    from backend.providers.asr.openai_whisper import OpenAIWhisperASR
    from backend.providers.nlp.anthropic import AnthropicNLP
    from backend.providers.nlp.openai_gpt import OpenAINLP
    from backend.providers.tts.elevenlabs import ElevenLabsTTS
    from backend.providers.tts.openai_tts import OpenAITTS

    registry.register_asr("deepgram", DeepgramASR)
    registry.register_asr("openai", OpenAIWhisperASR)
    registry.register_tts("elevenlabs", ElevenLabsTTS)
    registry.register_tts("openai", OpenAITTS)
    registry.register_nlp("anthropic", AnthropicNLP)
    registry.register_nlp("openai", OpenAINLP)
