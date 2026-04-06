"""Structured trace log — unified format for all pipeline events.

Every event in the pipeline (VAD, ASR, NLP, TTS, tool calls, etc.) is emitted
as a TraceLog with consistent fields. These logs feed into:
  1. stdout (structured JSON for log aggregation)
  2. trace_events DB table (for querying/monitoring)
  3. WebSocket broadcast (for real-time frontend)

ID hierarchy:
  trace_id     — conversation-level, 1 per session (= conversation_id)
  call_id      — turn-level, 1 per user→agent round-trip
  sentence_id  — LLM invocation within a turn (for multi-round tool calling)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger("sumi.trace")


@dataclass
class TraceLog:
    """Unified structured trace event."""

    # --- Identity ---
    trace_id: str             # conversation_id — session-level
    call_id: str              # turn-level ID (turn_index as string, or uuid)
    event: str                # e.g. "nlp.first_token", "asr.end", "tts.first_audio"
    agent_id: str = ""        # agent definition ID

    # --- Optional sub-IDs ---
    sentence_id: str = ""     # LLM invocation within a turn (0, 1, 2 for tool-call rounds)

    # --- Timing ---
    timestamp: float = 0.0    # epoch seconds
    duration_ms: float | None = None  # event duration (if applicable)

    # --- Request/Response ---
    request: dict[str, Any] = field(default_factory=dict)   # input/params for this event
    result: dict[str, Any] = field(default_factory=dict)    # output/metrics for this event

    # --- Auto-generated ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for DB/broadcast."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to compact JSON for stdout logging."""
        d = self.to_dict()
        # Remove empty optional fields for compactness
        return json.dumps(
            {k: v for k, v in d.items() if v is not None and v != "" and v != {} and v != 0.0 or k in ("trace_id", "call_id", "event")},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def log(self, level: int = logging.INFO):
        """Emit as structured log line."""
        # Human-readable summary
        parts = [f"[{self.event}]"]
        if self.duration_ms is not None:
            parts.append(f"dur={self.duration_ms:.0f}ms")

        # Key result fields inline
        for key in ("text", "transcript", "ttfb_ms", "ttf10t_ms", "score", "model",
                     "token_count", "ctx_messages", "ctx_tokens_est", "tool_name"):
            if key in self.result:
                v = self.result[key]
                if isinstance(v, str) and len(v) > 60:
                    v = v[:60] + "..."
                parts.append(f"{key}={v}")

        summary = " ".join(parts)
        logger.log(level, summary, extra={"trace_log": self.to_dict()})


@dataclass
class TraceContext:
    """Mutable context passed through a turn's lifecycle.

    Created at turn start, carries IDs and timing anchors.
    """

    trace_id: str             # = conversation_id
    agent_id: str
    call_id: str = ""         # set per turn
    sentence_id: str = "0"    # incremented per LLM invocation within turn

    # Timing anchors (epoch seconds)
    turn_start: float = 0.0   # when user started speaking (VAD start)
    vad_end: float = 0.0      # when user stopped speaking
    asr_final: float = 0.0    # when ASR produced final transcript
    nlp_start: float = 0.0    # when NLP started (thinking state)
    nlp_ttfb: float = 0.0     # first content token from LLM
    nlp_ttf10t: float = 0.0   # 10th content token from LLM
    tts_start: float = 0.0    # when TTS started
    tts_first_audio: float = 0.0  # first audio frame from TTS

    # Counters
    nlp_content_tokens: int = 0   # actual content tokens (not empty chunks)
    nlp_total_chunks: int = 0     # total stream chunks
    nlp_invocation: int = 0       # which LLM call within the turn (0-based)

    # Context size
    ctx_messages: int = 0         # number of messages in chat_ctx
    ctx_tokens_est: int = 0       # estimated token count

    def new_turn(self, turn_index: int) -> None:
        """Reset for a new turn."""
        self.call_id = str(turn_index)
        self.sentence_id = "0"
        self.turn_start = 0.0
        self.vad_end = 0.0
        self.asr_final = 0.0
        self.nlp_start = 0.0
        self.nlp_ttfb = 0.0
        self.nlp_ttf10t = 0.0
        self.tts_start = 0.0
        self.tts_first_audio = 0.0
        self.nlp_content_tokens = 0
        self.nlp_total_chunks = 0
        self.nlp_invocation = 0
        self.ctx_messages = 0
        self.ctx_tokens_est = 0

    def next_sentence(self) -> None:
        """Advance to next LLM invocation within turn (tool-call round)."""
        self.nlp_invocation += 1
        self.sentence_id = str(self.nlp_invocation)
        self.nlp_content_tokens = 0
        self.nlp_total_chunks = 0
        self.nlp_ttfb = 0.0
        self.nlp_ttf10t = 0.0

    def emit(self, event: str, *, duration_ms: float | None = None,
             request: dict | None = None, result: dict | None = None) -> TraceLog:
        """Create and log a TraceLog from this context."""
        log = TraceLog(
            trace_id=self.trace_id,
            call_id=self.call_id,
            sentence_id=self.sentence_id,
            event=event,
            agent_id=self.agent_id,
            duration_ms=duration_ms,
            request=request or {},
            result=result or {},
        )
        log.log()
        return log
