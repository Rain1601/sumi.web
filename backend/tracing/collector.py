"""Event collector: receives pipeline events, persists them, and broadcasts to WebSocket clients."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from backend.pipeline.events import PipelineEventType

if TYPE_CHECKING:
    from backend.tracing.trace_log import TraceLog

logger = logging.getLogger(__name__)


class EventCollector:
    """Collects trace events from the pipeline and distributes them."""

    def __init__(self):
        self._broadcaster = None
        self._batch_writer = None

    def emit(
        self,
        conversation_id: str,
        event_type: PipelineEventType,
        data: dict | None = None,
        duration_ms: float | None = None,
    ):
        """Emit a trace event (legacy interface)."""
        event = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "event_type": event_type.value,
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "data": data or {},
        }

        logger.debug(f"Trace event: {event_type.value} for {conversation_id}")
        self._dispatch(conversation_id, event)

    def emit_trace(self, trace_log: TraceLog):
        """Emit a structured TraceLog event."""
        d = trace_log.to_dict()
        # Map to the event dict format expected by broadcaster/batch_writer
        event = {
            "id": d["id"],
            "conversation_id": d["trace_id"],
            "event_type": d["event"],
            "timestamp": d["timestamp"],
            "duration_ms": d.get("duration_ms"),
            "data": {
                "trace_id": d["trace_id"],
                "call_id": d["call_id"],
                "sentence_id": d["sentence_id"],
                "agent_id": d["agent_id"],
                "request": d.get("request", {}),
                "result": d.get("result", {}),
            },
        }
        self._dispatch(d["trace_id"], event)

    def _dispatch(self, conversation_id: str, event: dict):
        """Send event to broadcaster and batch writer."""
        # Broadcast to WebSocket clients
        if self._broadcaster:
            self._broadcaster.broadcast(conversation_id, event)

        # Persist via batch writer
        if self._batch_writer:
            self._batch_writer.enqueue_event(event)

    def set_broadcaster(self, broadcaster):
        self._broadcaster = broadcaster

    def set_batch_writer(self, writer):
        self._batch_writer = writer


# Global instance
event_collector = EventCollector()
