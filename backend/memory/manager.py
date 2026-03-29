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

        # TODO: Extract structured facts via LLM summarization
        # This would call the NLP provider to extract key facts from the conversation
        # and upsert them into the memory_facts table
        logger.info(
            f"Processed conversation {conversation_id}: "
            f"{len(segments)} segments stored in vector memory"
        )

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
