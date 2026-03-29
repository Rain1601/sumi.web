"""ChromaDB vector store for semantic memory search."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VectorSearchResult:
    content: str
    score: float
    conversation_id: str | None
    timestamp: str | None


class VectorStore:
    """ChromaDB-backed vector store, one collection per user."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import chromadb
            from backend.config import settings
            self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        return self._client

    def _get_collection(self, user_id: str):
        client = self._get_client()
        return client.get_or_create_collection(
            name=f"memory_{user_id}",
            metadata={"hnsw:space": "cosine"},
        )

    async def add(
        self,
        user_id: str,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ):
        """Add text segments to a user's memory collection."""
        collection = self._get_collection(user_id)
        collection.add(
            documents=texts,
            metadatas=metadatas,
            ids=ids or [f"{user_id}_{i}" for i in range(len(texts))],
        )
        logger.info(f"Added {len(texts)} segments to memory for user {user_id}")

    async def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        """Search for relevant memory segments."""
        collection = self._get_collection(user_id)

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
        )

        search_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                search_results.append(VectorSearchResult(
                    content=doc,
                    score=1.0 - distance,  # Convert distance to similarity
                    conversation_id=metadata.get("conversation_id"),
                    timestamp=metadata.get("timestamp"),
                ))

        return search_results


# Global instance
vector_store = VectorStore()
