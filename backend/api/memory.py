from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import CurrentUserId, DbSession

router = APIRouter()


class MemoryFactResponse(BaseModel):
    id: str
    category: str
    key: str
    value: str
    confidence: float
    updated_at: str


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5


class MemorySearchResult(BaseModel):
    content: str
    score: float
    conversation_id: str | None
    timestamp: str | None


@router.get("/facts", response_model=list[MemoryFactResponse])
async def get_memory_facts(user_id: CurrentUserId, db: DbSession):
    """Get structured memory facts for the current user."""
    from sqlalchemy import select
    from backend.db.models import MemoryFact

    result = await db.execute(
        select(MemoryFact)
        .where(MemoryFact.user_id == user_id)
        .order_by(MemoryFact.updated_at.desc())
    )
    facts = result.scalars().all()
    return [
        MemoryFactResponse(
            id=f.id,
            category=f.category,
            key=f.key,
            value=f.value,
            confidence=f.confidence,
            updated_at=f.updated_at.isoformat(),
        )
        for f in facts
    ]


@router.post("/search", response_model=list[MemorySearchResult])
async def search_memory(req: MemorySearchRequest, user_id: CurrentUserId):
    """Search vector memory for relevant past context."""
    from backend.memory.vector import vector_store

    results = await vector_store.search(
        user_id=user_id,
        query=req.query,
        top_k=req.top_k,
    )
    return results
