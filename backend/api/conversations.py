from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.api.deps import Auth, DbSession

router = APIRouter()


class ConversationResponse(BaseModel):
    id: str
    agent_id: str
    language: str | None
    started_at: str
    ended_at: str | None
    summary: str | None


class PaginatedConversations(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tool_name: str | None
    is_truncated: bool
    started_at: str
    ended_at: str | None
    audio_url: str | None = None


def _to_response(c) -> ConversationResponse:
    return ConversationResponse(
        id=c.id,
        agent_id=c.agent_id,
        language=c.language,
        started_at=c.started_at.isoformat(),
        ended_at=c.ended_at.isoformat() if c.ended_at else None,
        summary=c.summary,
    )


@router.get("/", response_model=PaginatedConversations)
async def list_conversations(
    auth: Auth,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List conversations for the current user in current tenant."""
    from sqlalchemy import select, func
    from backend.db.models import Conversation

    # Total count
    count_q = select(func.count()).select_from(Conversation).where(
        Conversation.user_id == auth.user_id,
        Conversation.tenant_id == auth.tenant_id,
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Page query
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == auth.user_id, Conversation.tenant_id == auth.tenant_id)
        .order_by(Conversation.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    convs = result.scalars().all()

    return PaginatedConversations(
        items=[_to_response(c) for c in convs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/all", response_model=PaginatedConversations)
async def list_all_conversations(
    auth: Auth,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all conversations in current tenant (admin/QA view)."""
    from sqlalchemy import select, func
    from backend.db.models import Conversation

    count_q = select(func.count()).select_from(Conversation).where(
        Conversation.tenant_id == auth.tenant_id,
    )
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == auth.tenant_id)
        .order_by(Conversation.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    convs = result.scalars().all()

    return PaginatedConversations(
        items=[_to_response(c) for c in convs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, auth: Auth, db: DbSession):
    """Delete a conversation and its messages/traces (tenant-scoped)."""
    from sqlalchemy import delete, select
    from backend.db.models import Conversation, Message, TraceEvent

    # Verify exists and belongs to tenant
    conv = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == auth.tenant_id,
        )
    )
    if not conv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Delete related data
    await db.execute(delete(TraceEvent).where(TraceEvent.conversation_id == conversation_id))
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await db.commit()

    # Delete audio files if any
    import shutil
    from pathlib import Path
    audio_dir = Path(__file__).resolve().parent.parent.parent / "data" / "audio" / conversation_id
    if audio_dir.exists():
        shutil.rmtree(audio_dir)

    return {"ok": True}


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(conversation_id: str, auth: Auth, db: DbSession):
    """Get messages for a specific conversation (user + tenant scoped)."""
    from sqlalchemy import select
    from backend.db.models import Conversation, Message

    # Verify ownership
    conv = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == auth.user_id,
            Conversation.tenant_id == auth.tenant_id,
        )
    )
    if not conv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.started_at)
    )
    msgs = result.scalars().all()
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            tool_name=m.tool_name,
            is_truncated=m.is_truncated,
            started_at=m.started_at.isoformat(),
            ended_at=m.ended_at.isoformat() if m.ended_at else None,
            audio_url=m.audio_url,
        )
        for m in msgs
    ]
