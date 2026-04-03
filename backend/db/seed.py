"""Seed the database with initial data: SOTA models + default agents."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import settings
from backend.db.engine import async_session, init_db
from backend.db.models import Agent, ProviderModel, gen_uuid


# ─── SOTA Models (via AIHubMix) ─────────────────────────────────────────────

DEFAULT_MODELS = [
    # === NLP ===
    ProviderModel(id="nlp-claude-sonnet", name="Claude Sonnet 4", provider_type="nlp",
                  provider_name="anthropic", model_name="claude-sonnet-4-20250514",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-claude-haiku", name="Claude Haiku 4.5", provider_type="nlp",
                  provider_name="anthropic", model_name="claude-haiku-4-5-20251001",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-gpt4o", name="GPT-4o", provider_type="nlp",
                  provider_name="openai", model_name="gpt-4o",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-gpt4o-mini", name="GPT-4o Mini", provider_type="nlp",
                  provider_name="openai", model_name="gpt-4o-mini",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-gemini-pro", name="Gemini 2.5 Pro", provider_type="nlp",
                  provider_name="google", model_name="gemini-2.5-pro",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-gemini-flash", name="Gemini 2.5 Flash", provider_type="nlp",
                  provider_name="google", model_name="gemini-2.5-flash",
                  config={"temperature": 0.7, "max_tokens": 2048}),
    ProviderModel(id="nlp-deepseek", name="DeepSeek Chat", provider_type="nlp",
                  provider_name="deepseek", model_name="deepseek-chat",
                  config={"temperature": 0.7, "max_tokens": 4096}),
    ProviderModel(id="nlp-qwen-max", name="Qwen Max", provider_type="nlp",
                  provider_name="qwen", model_name="qwen-max",
                  config={"temperature": 0.7, "max_tokens": 4096}),

    # === ASR (Speech-to-Text) ===
    ProviderModel(id="asr-paraformer-v2", name="Paraformer Realtime v2", provider_type="asr",
                  provider_name="dashscope", model_name="paraformer-realtime-v2",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-paraformer-8k-v2", name="Paraformer Realtime 8k v2", provider_type="asr",
                  provider_name="dashscope", model_name="paraformer-realtime-8k-v2",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-funasr-realtime", name="FunASR 语音识别", provider_type="asr",
                  provider_name="dashscope", model_name="gummy-asr-realtime-v1",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-funasr-8k", name="FunASR 语音识别 8k", provider_type="asr",
                  provider_name="dashscope", model_name="gummy-asr-realtime-8k-v1",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-qwen3-flash", name="Qwen3-ASR-Flash", provider_type="asr",
                  provider_name="dashscope", model_name="qwen3-asr-flash-realtime",
                  config={"language": "zh", "max_sentence_silence": 600}),
    ProviderModel(id="asr-whisper", name="Whisper Large", provider_type="asr",
                  provider_name="openai", model_name="whisper-1",
                  config={"language": "zh"}),

    # === TTS (Text-to-Speech, realtime) ===
    ProviderModel(id="tts-cosyvoice-v35-flash", name="CosyVoice v3.5 Flash", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3.5-flash",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-cosyvoice-v35-plus", name="CosyVoice v3.5 Plus", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3.5-plus",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-cosyvoice-flash", name="CosyVoice v3 Flash", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-flash",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-cosyvoice-plus", name="CosyVoice v3 Plus", provider_type="tts",
                  provider_name="dashscope", model_name="cosyvoice-v3-plus",
                  config={"voice": "longanyang"}),
    ProviderModel(id="tts-openai-alloy", name="OpenAI TTS - Alloy", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "alloy"}),
    ProviderModel(id="tts-openai-nova", name="OpenAI TTS - Nova", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "nova"}),
    ProviderModel(id="tts-openai-shimmer", name="OpenAI TTS - Shimmer", provider_type="tts",
                  provider_name="openai", model_name="tts-1",
                  config={"voice": "shimmer"}),
    ProviderModel(id="tts-4o-mini-coral", name="TTS-4o Mini - Coral (Realtime)", provider_type="tts",
                  provider_name="openai", model_name="tts-4o-mini",
                  config={"voice": "coral"}),
    ProviderModel(id="tts-4o-mini-sage", name="TTS-4o Mini - Sage (Realtime)", provider_type="tts",
                  provider_name="openai", model_name="tts-4o-mini",
                  config={"voice": "sage"}),
]

# ─── Default Agents ──────────────────────────────────────────────────────────

DEFAULT_AGENTS = [
    Agent(
        id="default",
        name_zh="默认助手",
        name_en="Default Assistant",
        description_zh="通用语音对话助手，支持中英双语",
        description_en="General-purpose voice assistant with bilingual support",
        system_prompt=(
            "You are Sumi, a friendly and helpful voice assistant. "
            "You speak naturally and concisely. "
            "You can communicate in both Chinese and English, "
            "and you automatically respond in the language the user speaks. "
            "Keep your responses brief since this is a voice conversation."
        ),
        asr_model_id="asr-paraformer-v2",
        tts_model_id="tts-cosyvoice-flash",
        nlp_model_id="nlp-claude-sonnet",
        asr_provider="openai", asr_config={},
        tts_provider="openai", tts_config={},
        nlp_provider="anthropic", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.5},
        tools=["get_current_datetime"],
        interruption_policy="always",
        language="auto",
        opening_line="你好，我是Sumi，有什么可以帮你的吗？",
        status="published",
        version=1,
        is_active=True,
    ),
    Agent(
        id="english_tutor",
        name_zh="英语导师",
        name_en="English Tutor",
        description_zh="英语口语练习助手，帮助提升英语会话能力",
        description_en="English speaking practice assistant",
        system_prompt=(
            "You are an English language tutor named Sumi. "
            "Always respond in English. If the user speaks Chinese, "
            "gently encourage them to try in English and provide the English translation. "
            "Correct grammar mistakes naturally within the conversation. "
            "Keep responses conversational and encouraging."
        ),
        asr_model_id="asr-whisper",
        tts_model_id="tts-openai-alloy",
        nlp_model_id="nlp-gpt4o",
        asr_provider="openai", asr_config={},
        tts_provider="openai", tts_config={},
        nlp_provider="openai", nlp_config={},
        vad_mode="backend",
        vad_config={"min_speech_duration": 0.1, "min_silence_duration": 0.8},
        tools=["get_current_datetime"],
        interruption_policy="sentence_boundary",
        language="en",
        opening_line="Hi there! I'm Sumi, your English tutor. What would you like to practice today?",
        status="published",
        version=1,
        is_active=True,
    ),
]


async def seed():
    settings.db_path.mkdir(parents=True, exist_ok=True)
    await init_db()

    async with async_session() as session:
        from sqlalchemy import select

        # Seed models
        for model in DEFAULT_MODELS:
            existing = await session.execute(
                select(ProviderModel).where(ProviderModel.id == model.id)
            )
            if existing.scalar_one_or_none():
                print(f"  Model '{model.id}' exists, skipping")
                continue
            session.add(model)
            print(f"  + Model: [{model.provider_type}] {model.name} ({model.model_name})")

        # Seed agents
        for agent in DEFAULT_AGENTS:
            existing = await session.execute(
                select(Agent).where(Agent.id == agent.id)
            )
            if existing.scalar_one_or_none():
                print(f"  Agent '{agent.id}' exists, skipping")
                continue
            session.add(agent)
            print(f"  + Agent: {agent.name_en}")

        await session.commit()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
