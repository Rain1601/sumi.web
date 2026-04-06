"""Unified provider factory — the single pluggable layer.

All providers register here. The worker calls `create_stt/create_llm/create_tts`
with model_info from DB, and gets back a LiveKit-compatible plugin instance.

To add a new provider:
  1. Write an adapter that implements LiveKit's stt.STT / llm.LLM / tts.TTS
  2. Register it in `_REGISTRY` below with a provider_name key
  3. Done — it's now selectable from the Models page
"""

import logging
from typing import Any, Callable

from livekit.agents import stt, llm, tts

from backend.config import settings

logger = logging.getLogger(__name__)

# Type aliases for factory functions
STTFactory = Callable[[dict], stt.STT]
LLMFactory = Callable[[dict], llm.LLM]
TTSFactory = Callable[[dict], tts.TTS]


# ─── STT Factories ──────────────────────────────────────────────────────────

def _stt_dashscope(m: dict) -> stt.STT:
    model_name = m.get("model_name", "paraformer-realtime-v2")

    # Realtime API models (OpenAI-compatible protocol)
    if "realtime" in model_name and ("qwen" in model_name or "fun-asr" in model_name):
        from backend.providers.asr.dashscope_realtime import DashScopeRealtimeSTT
        return DashScopeRealtimeSTT(
            model=model_name,
            language=m.get("config", {}).get("language", "zh"),
            vad_threshold=m.get("config", {}).get("vad_threshold", 0.5),
            silence_duration_ms=m.get("config", {}).get("silence_duration_ms", 400),
        )

    # Legacy inference API models (Paraformer)
    from backend.providers.asr.dashscope_paraformer import ParaformerSTT
    return ParaformerSTT(
        model=model_name,
        language=m.get("config", {}).get("language", "zh"),
        max_sentence_silence=m.get("config", {}).get("max_sentence_silence", 600),
    )


def _stt_openai(m: dict) -> stt.STT:
    from livekit.plugins import openai
    return openai.STT(
        model=m.get("model_name", "whisper-1"),
        language=m.get("config", {}).get("language", "zh"),
        base_url=settings.aihubmix_base_url,
        api_key=settings.aihubmix_api_key,
    )


# ─── LLM Factories ──────────────────────────────────────────────────────────

def _llm_aihubmix(m: dict) -> llm.LLM:
    """LLM via AIHubMix (OpenAI-compatible)."""
    from livekit.plugins import openai
    return openai.LLM(
        model=m.get("model_name", "gpt-4o-mini"),
        temperature=m.get("config", {}).get("temperature", 0.7),
        base_url=settings.aihubmix_base_url,
        api_key=settings.aihubmix_api_key,
    )


def _llm_dashscope(m: dict) -> llm.LLM:
    """LLM via DashScope direct (OpenAI-compatible mode, lower latency for qwen)."""
    from livekit.plugins import openai
    return openai.LLM(
        model=m.get("model_name", "qwen2.5-72b-instruct"),
        temperature=m.get("config", {}).get("temperature", 0.7),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=settings.dashscope_api_key,
    )


# ─── TTS Factories ──────────────────────────────────────────────────────────

def _tts_dashscope(m: dict) -> tts.TTS:
    from backend.providers.tts.dashscope_cosyvoice import CosyVoiceTTS
    return CosyVoiceTTS(
        model=m.get("model_name", "cosyvoice-v3-flash"),
        voice=m.get("config", {}).get("voice", "longanyang"),
    )


def _tts_openai(m: dict) -> tts.TTS:
    from livekit.plugins import openai
    return openai.TTS(
        model=m.get("model_name", "tts-1"),
        voice=m.get("config", {}).get("voice", "nova"),
        base_url=settings.aihubmix_base_url,
        api_key=settings.aihubmix_api_key,
    )


# ─── Registry ───────────────────────────────────────────────────────────────

_STT_REGISTRY: dict[str, STTFactory] = {
    "dashscope": _stt_dashscope,
    "openai": _stt_openai,
}

_LLM_REGISTRY: dict[str, LLMFactory] = {
    "dashscope": _llm_dashscope,  # Direct to DashScope (lowest latency for qwen)
    "anthropic": _llm_aihubmix,
    "openai": _llm_aihubmix,
    "google": _llm_aihubmix,
    "deepseek": _llm_aihubmix,
    "qwen": _llm_aihubmix,
}

_TTS_REGISTRY: dict[str, TTSFactory] = {
    "dashscope": _tts_dashscope,
    "openai": _tts_openai,
}


def register_stt(provider_name: str, factory: STTFactory):
    _STT_REGISTRY[provider_name] = factory


def register_llm(provider_name: str, factory: LLMFactory):
    _LLM_REGISTRY[provider_name] = factory


def register_tts(provider_name: str, factory: TTSFactory):
    _TTS_REGISTRY[provider_name] = factory


# ─── Create functions (called by worker) ─────────────────────────────────────

def create_stt(model_info: dict | None, *, voiceprint: bool = False, voiceprint_model: str = "resemblyzer", voiceprint_threshold: float = 0.65) -> stt.STT:
    m = model_info or {}
    provider = m.get("provider_name", "dashscope")
    factory = _STT_REGISTRY.get(provider)
    if not factory:
        raise ValueError(f"Unknown STT provider: {provider}. Available: {list(_STT_REGISTRY)}")
    instance = factory(m)
    logger.info(f"[ASR INIT] provider={provider} model={m.get('model_name', '?')}")

    if voiceprint:
        from backend.pipeline.voiceprint_stt import VoiceprintSTT
        instance = VoiceprintSTT(instance, model=voiceprint_model, threshold=voiceprint_threshold)
        logger.info(f"[VOICEPRINT] Enabled: model={voiceprint_model} threshold={voiceprint_threshold}")

    return instance


def create_llm(model_info: dict | None) -> llm.LLM:
    m = model_info or {}
    provider = m.get("provider_name", "openai")
    factory = _LLM_REGISTRY.get(provider)
    if not factory:
        raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(_LLM_REGISTRY)}")
    instance = factory(m)
    logger.info(f"[NLP INIT] provider={provider} model={m.get('model_name', '?')}")
    return instance


def create_tts(model_info: dict | None) -> tts.TTS:
    m = model_info or {}
    provider = m.get("provider_name", "dashscope")
    factory = _TTS_REGISTRY.get(provider)
    if not factory:
        raise ValueError(f"Unknown TTS provider: {provider}. Available: {list(_TTS_REGISTRY)}")
    instance = factory(m)
    logger.info(f"[TTS INIT] provider={provider} model={m.get('model_name', '?')}")
    return instance


def has_builtin_vad(model_info: dict | None) -> bool:
    """Return True for providers with reliable server-side VAD (DashScope Realtime,
    Paraformer), so LiveKit skips Silero and relies on the STT's own VAD events.
    This avoids dual-VAD conflicts that fragment Chinese speech.
    """
    m = model_info or {}
    provider = m.get("provider_name", "")
    if provider == "dashscope":
        return True  # DashScope Realtime & Paraformer both have server-side VAD
    return False
