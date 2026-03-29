"""Trace event data models for the tracing system."""

from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.events import PipelineEventType


@dataclass
class TraceEventData:
    """A single trace event."""
    id: str
    conversation_id: str
    event_type: PipelineEventType
    timestamp: float
    duration_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceSpan:
    """A span grouping related events (e.g., a full ASR cycle)."""
    id: str
    conversation_id: str
    name: str
    start_time: float
    end_time: float | None = None
    events: list[TraceEventData] = field(default_factory=list)

    @property
    def duration_ms(self) -> float | None:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
