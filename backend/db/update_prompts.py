"""One-off script to update existing agents with production-grade prompts."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.db.engine import async_session, init_db
from backend.db.models import Agent
from sqlalchemy import select

from backend.services.prompts.customer_service import SYSTEM_PROMPT as CS_PROMPT
from backend.services.prompts.sales_agent import SYSTEM_PROMPT as SALES_PROMPT
from backend.services.prompts.restaurant_booking import SYSTEM_PROMPT as RESTAURANT_PROMPT
from backend.services.prompts.medical_triage import SYSTEM_PROMPT as MEDICAL_PROMPT
from backend.services.prompts.debt_collection import SYSTEM_PROMPT as DEBT_PROMPT
from backend.services.prompts.game_npc import SYSTEM_PROMPT as GAME_PROMPT
from backend.services.prompts.emotional_companion import SYSTEM_PROMPT as COMPANION_PROMPT

UPDATES = {
    "customer_service": CS_PROMPT,
    "sales_agent": SALES_PROMPT,
    "restaurant_booking": RESTAURANT_PROMPT,
    "medical_triage": MEDICAL_PROMPT,
    "debt_collection": DEBT_PROMPT,
    "game_npc": GAME_PROMPT,
    "emotional_companion": COMPANION_PROMPT,
}


async def main():
    await init_db()
    async with async_session() as session:
        for agent_id, prompt in UPDATES.items():
            result = await session.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent:
                agent.system_prompt = prompt
                print(f"  ✓ {agent_id}: updated ({len(prompt)} chars)")
            else:
                print(f"  ✗ {agent_id}: not found")
        await session.commit()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
