"""QA Recall Engine — embedding-based question-answer pair matching.

Used by skills with skill_type="qa". User's question is embedded and matched
against pre-defined question patterns via cosine similarity.
"""

import logging
import numpy as np
from typing import Any

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    return float(dot / norm) if norm > 0 else 0.0


class QARecallEngine:
    """Embedding-based QA pair matching for skill execution."""

    def __init__(self, qa_config: dict[str, Any]):
        """
        Args:
            qa_config: {pairs: [...], embedding_model: "...", fallback: "free"}
        """
        self._pairs: list[dict] = qa_config.get("pairs", [])
        self._fallback: str = qa_config.get("fallback", "free")
        self._embeddings: dict[str, list[float]] = {}
        self._initialized = False

    async def initialize(self):
        """Pre-compute embeddings for all question patterns."""
        if self._initialized or not self._pairs:
            return

        all_patterns = []
        for pair in self._pairs:
            all_patterns.extend(pair.get("question_patterns", []))

        if not all_patterns:
            return

        embeddings = await self._batch_embed(all_patterns)
        self._embeddings = dict(zip(all_patterns, embeddings))
        self._initialized = True
        logger.info(f"[QA_RECALL] Initialized {len(all_patterns)} pattern embeddings")

    async def recall(self, user_query: str, threshold: float = 0.75) -> dict | None:
        """Find best matching QA pair for user query.

        Returns: {pair: {...}, score: float} or None if no match above threshold.
        """
        if not self._initialized:
            await self.initialize()

        if not self._embeddings:
            return None

        query_emb = await self._embed(user_query)
        if not query_emb:
            return None

        best_score = 0.0
        best_pair = None

        for pair in self._pairs:
            for pattern in pair.get("question_patterns", []):
                if pattern in self._embeddings:
                    score = _cosine_similarity(query_emb, self._embeddings[pattern])
                    if score > best_score:
                        best_score = score
                        best_pair = pair

        if best_score >= threshold and best_pair:
            logger.info(f"[QA_RECALL] Match: score={best_score:.3f} pair_id={best_pair.get('id', '?')}")
            return {"pair": best_pair, "score": best_score}

        logger.debug(f"[QA_RECALL] No match: best_score={best_score:.3f} threshold={threshold}")
        return None

    def build_qa_prompt(self, match: dict) -> str:
        """Build prompt injection from a matched QA pair."""
        pair = match["pair"]
        parts = [f"参考答案（匹配度 {match['score']:.0%}）：", pair.get("answer", "")]
        if pair.get("followup"):
            parts.append(f"追问引导：{pair['followup']}")
        return "\n".join(parts)

    async def _embed(self, text: str) -> list[float] | None:
        """Embed a single text string."""
        results = await self._batch_embed([text])
        return results[0] if results else None

    async def _batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts using DashScope text-embedding API.

        Falls back to a simple TF-IDF-like approach if the API is unavailable.
        """
        try:
            from openai import AsyncOpenAI
            from backend.config import settings

            client = AsyncOpenAI(
                api_key=settings.dashscope_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            resp = await client.embeddings.create(
                model="text-embedding-v3",
                input=texts,
            )
            return [item.embedding for item in resp.data]
        except Exception as e:
            logger.warning(f"[QA_RECALL] Embedding API failed: {e}, using fallback")
            return self._fallback_embed(texts)

    @staticmethod
    def _fallback_embed(texts: list[str]) -> list[list[float]]:
        """Simple character-level hash embedding as fallback."""
        dim = 256
        embeddings = []
        for text in texts:
            vec = np.zeros(dim)
            for i, ch in enumerate(text):
                idx = ord(ch) % dim
                vec[idx] += 1.0 / (i + 1)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist())
        return embeddings
