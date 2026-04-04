"""Memory manager: orchestrates hybrid structured + vector memory."""

import logging
from datetime import datetime

from backend.memory.vector import vector_store

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates the hybrid memory system.

    - Structured facts (SQLite): key-value facts about the user
    - Vector store (ChromaDB): semantic search over conversation history
    """

    async def build_context(self, user_id: str, current_topic: str | None = None) -> str:
        """Build memory context string to inject into system prompt."""
        parts = []

        # Load structured facts
        facts = await self._load_facts(user_id)
        if facts:
            parts.append("## Known facts about the user:")
            for f in facts:
                parts.append(f"- [{f['category']}] {f['key']}: {f['value']}")

        # Search relevant vector memories
        if current_topic:
            results = await vector_store.search(user_id, current_topic, top_k=3)
            if results:
                parts.append("\n## Relevant past conversation context:")
                for r in results:
                    parts.append(f"- (relevance: {r.score:.2f}) {r.content}")

        if not parts:
            return ""

        return "\n".join(parts)

    async def process_conversation(
        self,
        user_id: str,
        conversation_id: str,
        messages: list[dict],
    ):
        """Process a completed conversation: extract facts + store embeddings."""
        # Store conversation segments as vectors
        segments = []
        metadatas = []
        ids = []

        for i, msg in enumerate(messages):
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                segments.append(f"{msg['role']}: {msg['content']}")
                metadatas.append({
                    "conversation_id": conversation_id,
                    "role": msg["role"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                ids.append(f"{conversation_id}_{i}")

        if segments:
            await vector_store.add(user_id, segments, metadatas, ids)

        # Extract structured facts via LLM summarization
        await self.extract_facts(user_id, conversation_id, messages)

        logger.info(
            f"Processed conversation {conversation_id}: "
            f"{len(segments)} segments stored in vector memory"
        )

    async def extract_facts(self, user_id: str, conversation_id: str, messages: list[dict]):
        """Use LLM to extract key facts from conversation and save to DB."""
        if not messages:
            return

        # Build conversation text
        conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        # Call LLM to extract facts
        import httpx
        from backend.config import settings

        prompt = f"""从以下对话中提取关于用户的关键信息。返回JSON数组，每项包含 category, key, value。
category 可选: preference, fact, goal, context
只提取确定的信息，不要猜测。如果没有有用信息，返回空数组 []。

对话内容:
{conv_text[:2000]}

返回格式: [{{"category": "...", "key": "...", "value": "..."}}]"""

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.dashscope_base_url or 'https://dashscope.aliyuncs.com/compatible-mode/v1'}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
                    json={
                        "model": "qwen-turbo",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 500,
                    },
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                # Parse JSON from response
                import json, re
                # Try to find JSON array in response
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    facts = json.loads(match.group())
                else:
                    return

                # Upsert facts to DB
                from backend.db.engine import async_session as get_session
                from backend.db.models import MemoryFact, gen_uuid
                from sqlalchemy import select

                async with get_session() as db:
                    for f in facts:
                        if not all(k in f for k in ("category", "key", "value")):
                            continue
                        # Upsert
                        existing = await db.execute(
                            select(MemoryFact).where(
                                MemoryFact.user_id == user_id,
                                MemoryFact.category == f["category"],
                                MemoryFact.key == f["key"],
                            )
                        )
                        row = existing.scalar_one_or_none()
                        if row:
                            row.value = f["value"]
                            row.source_conversation_id = conversation_id
                        else:
                            db.add(MemoryFact(
                                id=gen_uuid(),
                                user_id=user_id,
                                category=f["category"],
                                key=f["key"],
                                value=f["value"],
                                source_conversation_id=conversation_id,
                            ))
                    await db.commit()
                    logger.info(f"Extracted {len(facts)} facts for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to extract facts: {e}")

    async def _load_facts(self, user_id: str) -> list[dict]:
        """Load structured facts from the database."""
        from sqlalchemy import select
        from backend.db.engine import async_session
        from backend.db.models import MemoryFact

        async with async_session() as session:
            result = await session.execute(
                select(MemoryFact)
                .where(MemoryFact.user_id == user_id)
                .order_by(MemoryFact.updated_at.desc())
                .limit(20)
            )
            facts = result.scalars().all()
            return [
                {
                    "category": f.category,
                    "key": f.key,
                    "value": f.value,
                    "confidence": f.confidence,
                }
                for f in facts
            ]


# Global instance
memory_manager = MemoryManager()
