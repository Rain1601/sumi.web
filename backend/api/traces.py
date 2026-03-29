from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.api.deps import DbSession

router = APIRouter()


class TraceEventResponse(BaseModel):
    id: str
    event_type: str
    timestamp: float
    duration_ms: float | None
    data: dict | None


@router.get("/{conversation_id}", response_model=list[TraceEventResponse])
async def get_traces(conversation_id: str, db: DbSession):
    """Get trace events for a conversation."""
    from sqlalchemy import select
    from backend.db.models import TraceEvent

    result = await db.execute(
        select(TraceEvent)
        .where(TraceEvent.conversation_id == conversation_id)
        .order_by(TraceEvent.timestamp)
    )
    events = result.scalars().all()
    return [
        TraceEventResponse(
            id=e.id,
            event_type=e.event_type,
            timestamp=e.timestamp,
            duration_ms=e.duration_ms,
            data=e.data,
        )
        for e in events
    ]


@router.websocket("/ws/{conversation_id}")
async def trace_websocket(websocket: WebSocket, conversation_id: str):
    """Real-time trace event stream via WebSocket."""
    await websocket.accept()

    from backend.tracing.broadcaster import trace_broadcaster

    async def on_event(event: dict):
        try:
            await websocket.send_json(event)
        except Exception:
            pass

    trace_broadcaster.subscribe(conversation_id, on_event)
    try:
        # Keep connection alive, client can send ping
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        trace_broadcaster.unsubscribe(conversation_id, on_event)
