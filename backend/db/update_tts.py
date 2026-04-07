"""One-off script to upgrade all agents to CosyVoice v3.5 with per-scenario voices."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.db.engine import async_session, init_db
from backend.db.models import Agent
from sqlalchemy import select

# agent_id -> (tts_model_id, voice)
VOICE_MAP = {
    "default":            ("tts-cosyvoice-v35-flash", "longshu"),        # 温暖女声 — 通用助手
    "english_tutor":      ("tts-openai-alloy", "alloy"),                 # 保持 OpenAI 英文音色
    "customer_service":   ("tts-cosyvoice-v35-flash", "longxiaochun"),   # 甜美女声 — 客服小美
    "sales_agent":        ("tts-cosyvoice-v35-flash", "longanyang"),     # 沉稳男声 — 电销小李
    "restaurant_booking": ("tts-cosyvoice-v35-flash", "longxiaochun"),   # 甜美女声 — 前台小雨
    "medical_triage":     ("tts-cosyvoice-v35-flash", "longyue"),        # 知性女声 — 分诊护士
    "debt_collection":    ("tts-cosyvoice-v35-flash", "longanyang"),     # 沉稳男声 — 催收专员
    "psych_support":      ("tts-cosyvoice-v35-flash", "longshu"),        # 温暖女声 — 心理热线
    "insurance_renewal":  ("tts-cosyvoice-v35-flash", "longanyang"),     # 沉稳男声 — 续保顾问
    "game_npc":           ("tts-cosyvoice-v35-flash", "longjielidou"),   # 少年音 — 矮人酒馆老板
    "emotional_companion":("tts-cosyvoice-v35-flash", "longxiaoxia"),    # 活泼女声 — 小夏
}


async def main():
    await init_db()
    async with async_session() as session:
        for agent_id, (tts_model_id, voice) in VOICE_MAP.items():
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent:
                agent.tts_model_id = tts_model_id
                # Update voice in tts_config
                cfg = agent.tts_config if isinstance(agent.tts_config, dict) else {}
                cfg["voice"] = voice
                agent.tts_config = cfg
                print(f"  ✓ {agent_id}: {tts_model_id} / {voice}")
            else:
                print(f"  ✗ {agent_id}: not found")
        await session.commit()
    print("\nDone. All agents upgraded to CosyVoice v3.5 with per-scenario voices.")


if __name__ == "__main__":
    asyncio.run(main())
