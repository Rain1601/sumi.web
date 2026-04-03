"""Event collector: receives pipeline events, persists them, and broadcasts to WebSocket clients."""

import logging
import time
import uuid

from backend.pipeline.events import PipelineEventType

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
        """Emit a trace event."""
        event = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "event_type": event_type.value,
            "timestamp": time.time(),
            "duration_ms": duration_ms,
            "data": data or {},
        }

        logger.debug(f"Trace event: {event_type.value} for {conversation_id}")

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
