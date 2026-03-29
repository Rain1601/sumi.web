"""Event collector: receives pipeline events, persists them, and broadcasts to WebSocket clients."""

import logging
import time
import uuid

from backend.pipeline.events import PipelineEventType

logger = logging.getLogger(__name__)


class EventCollector:
    """Collects trace events from the pipeline and distributes them."""

    def __init__(self):
        self._buffer: list[dict] = []
        self._broadcaster = None

    def emit(
        self,
        conversation_id: str,
        event_type: PipelineEventType,
        data: dict | None = None,
        duration_ms: float | None = None,
    ):
        """Emit a trace event."""
        event = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "event_type": event_type.value,
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "data": data or {},
        }

        self._buffer.append(event)
        logger.debug(f"Trace event: {event_type.value} for {conversation_id}")

        # Broadcast to WebSocket clients
        if self._broadcaster:
            self._broadcaster.broadcast(conversation_id, event)

    def set_broadcaster(self, broadcaster):
        self._broadcaster = broadcaster

    def flush(self) -> list[dict]:
        """Flush buffered events for batch persistence."""
        events = self._buffer.copy()
        self._buffer.clear()
        return events


# Global instance
event_collector = EventCollector()
