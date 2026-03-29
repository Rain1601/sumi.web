from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import CurrentUserId, DbSession

router = APIRouter()


class ConversationResponse(BaseModel):
    id: str
    agent_id: str
    language: str | None
    started_at: str
    ended_at: str | None
    summary: str | None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tool_name: str | None
    is_truncated: bool
    started_at: str
    ended_at: str | None


@router.get("/", response_model=list[ConversationResponse])
async def list_conversations(user_id: CurrentUserId, db: DbSession):
    """List conversations for the current user."""
    from sqlalchemy import select
    from backend.db.models import Conversation

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.started_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        ConversationResponse(
            id=c.id,
            agent_id=c.agent_id,
            language=c.language,
            started_at=c.started_at.isoformat(),
            ended_at=c.ended_at.isoformat() if c.ended_at else None,
            summary=c.summary,
        )
        for c in convs
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(conversation_id: str, user_id: CurrentUserId, db: DbSession):
    """Get messages for a specific conversation."""
    from sqlalchemy import select
    from backend.db.models import Conversation, Message

    # Verify ownership
    conv = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if not conv.scalar_one_or_none():
        from fastapi import HTTPException
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
        )
        for m in msgs
    ]
