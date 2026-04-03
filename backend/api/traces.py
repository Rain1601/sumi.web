from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession

router = APIRouter()


class TraceEventResponse(BaseModel):
    id: str
    event_type: str
    timestamp: float
    duration_ms: float | None
    data: dict | None


class TurnUserData(BaseModel):
    text: str
    vad_duration_ms: float | None = None
    asr_latency_ms: float | None = None
    timestamp: float


class TurnAgentData(BaseModel):
    text: str
    nlp_ttfb_ms: float | None = None
    nlp_total_ms: float | None = None
    tts_first_audio_ms: float | None = None
    tts_total_ms: float | None = None
    tool_calls: list = []


class TurnResponse(BaseModel):
    index: int
    user: TurnUserData | None = None
    agent: TurnAgentData | None = None
    events: list[TraceEventResponse] = []


class LatencySummary(BaseModel):
    total_turns: int
    total_duration_s: float | None = None
    error_count: int = 0
    asr_avg_ms: float | None = None
    nlp_ttfb_avg_ms: float | None = None
    tts_first_audio_avg_ms: float | None = None
    e2e_avg_ms: float | None = None


@router.get("/{conversation_id}", response_model=list[TraceEventResponse])
async def get_traces(conversation_id: str, db: DbSession):
    """Get trace events for a conversation."""
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


@router.get("/{conversation_id}/turns", response_model=list[TurnResponse])
async def get_turns(conversation_id: str, db: DbSession):
    """Get trace events grouped by turn."""
    from backend.db.models import TraceEvent

    result = await db.execute(
        select(TraceEvent)
        .where(TraceEvent.conversation_id == conversation_id)
        .order_by(TraceEvent.timestamp)
    )
    all_events = result.scalars().all()

    # Group events by turn_index from data field
    turns_map: dict[int, TurnResponse] = {}
    # Track events without a turn_index — assign to the latest turn
    current_turn_index = 0

    for e in all_events:
        data = e.data or {}
        turn_index = data.get("turn_index", current_turn_index)

        if turn_index not in turns_map:
            turns_map[turn_index] = TurnResponse(index=turn_index)

        turn = turns_map[turn_index]

        event_resp = TraceEventResponse(
            id=e.id,
            event_type=e.event_type,
            timestamp=e.timestamp,
            duration_ms=e.duration_ms,
            data=e.data,
        )
        turn.events.append(event_resp)

        if e.event_type == "turn.user_complete":
            turn.user = TurnUserData(
                text=data.get("text", ""),
                vad_duration_ms=data.get("vad_duration_ms"),
                asr_latency_ms=data.get("asr_latency_ms") or e.duration_ms,
                timestamp=e.timestamp,
            )
            current_turn_index = turn_index
        elif e.event_type == "turn.agent_complete":
            turn.agent = TurnAgentData(
                text=data.get("text", ""),
                nlp_ttfb_ms=data.get("nlp_ttfb_ms"),
                nlp_total_ms=data.get("nlp_total_ms") or e.duration_ms,
                tts_first_audio_ms=data.get("tts_first_audio_ms"),
                tts_total_ms=data.get("tts_total_ms"),
                tool_calls=data.get("tool_calls", []),
            )
            current_turn_index = turn_index + 1

    # Return sorted by turn index
    return sorted(turns_map.values(), key=lambda t: t.index)


@router.get("/{conversation_id}/summary", response_model=LatencySummary)
async def get_summary(conversation_id: str, db: DbSession):
    """Latency statistics for a session."""
    from backend.db.models import TraceEvent

    result = await db.execute(
        select(TraceEvent)
        .where(TraceEvent.conversation_id == conversation_id)
        .order_by(TraceEvent.timestamp)
    )
    all_events = result.scalars().all()

    if not all_events:
        return LatencySummary(total_turns=0)

    asr_latencies = []
    nlp_ttfbs = []
    tts_firsts = []
    e2e_latencies = []
    error_count = 0
    turn_indices = set()

    first_ts = all_events[0].timestamp
    last_ts = all_events[-1].timestamp

    for e in all_events:
        data = e.data or {}
        turn_idx = data.get("turn_index")
        if turn_idx is not None:
            turn_indices.add(turn_idx)

        if e.event_type == "turn.user_complete":
            asr_ms = data.get("asr_latency_ms") or e.duration_ms
            if asr_ms is not None:
                asr_latencies.append(asr_ms)

        elif e.event_type == "turn.agent_complete":
            nlp_ttfb = data.get("nlp_ttfb_ms")
            if nlp_ttfb is not None:
                nlp_ttfbs.append(nlp_ttfb)

            tts_first = data.get("tts_first_audio_ms")
            if tts_first is not None:
                tts_firsts.append(tts_first)

            # E2E = sum of ASR + NLP + TTS for this turn
            e2e = 0.0
            has_any = False
            asr_ms = data.get("asr_latency_ms")
            if asr_ms:
                e2e += asr_ms
                has_any = True
            nlp_total = data.get("nlp_total_ms") or e.duration_ms
            if nlp_total:
                e2e += nlp_total
                has_any = True
            tts_total = data.get("tts_total_ms")
            if tts_total:
                e2e += tts_total
                has_any = True
            if has_any:
                e2e_latencies.append(e2e)

        elif e.event_type.endswith(".error"):
            error_count += 1

    def avg(lst: list[float]) -> float | None:
        return round(sum(lst) / len(lst), 1) if lst else None

    return LatencySummary(
        total_turns=len(turn_indices) or max(1, len([e for e in all_events if e.event_type == "turn.user_complete"])),
        total_duration_s=round(last_ts - first_ts, 1) if last_ts > first_ts else None,
        error_count=error_count,
        asr_avg_ms=avg(asr_latencies),
        nlp_ttfb_avg_ms=avg(nlp_ttfbs),
        tts_first_audio_avg_ms=avg(tts_firsts),
        e2e_avg_ms=avg(e2e_latencies),
    )


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
