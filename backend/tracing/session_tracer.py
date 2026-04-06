"""Session-level tracer — attaches to AgentSession, emits structured TraceLog events.

All pipeline events (VAD, ASR, NLP, TTS, tools, memory, interruptions, lifecycle)
flow through TraceContext.emit() → TraceLog → EventCollector → broadcaster + DB.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from livekit.agents.voice import AgentSession

from backend.tracing.audio_recorder import AudioRecorder
from backend.tracing.collector import event_collector
from backend.tracing.trace_log import TraceContext
from backend.tracing.schemas import ToolCallData

logger = logging.getLogger(__name__)


class SessionTracer:
    def __init__(
        self,
        conversation_id: str,
        room_name: str,
        user_id: str,
        agent_id: str,
    ):
        self._conversation_id = conversation_id
        self._room_name = room_name
        self._user_id = user_id
        self._agent_id = agent_id
        self._turn_index = 0
        self._session_start = time.time()

        # Structured trace context — carries IDs + timing anchors
        self._ctx = TraceContext(
            trace_id=conversation_id,
            agent_id=agent_id,
        )

        # Per-turn state
        self._nlp_text = ""
        self._agent_spoken_text = ""
        self._tool_calls: list[ToolCallData] = []

        # Audio recorder
        self._audio_recorder = AudioRecorder(conversation_id)
        self._user_audio_urls: dict[int, str] = {}
        self._agent_audio_urls: dict[int, str] = {}

    @property
    def ctx(self) -> TraceContext:
        """Expose TraceContext for InstrumentedLLM/TTS."""
        return self._ctx

    def _emit(self, event: str, *, duration_ms: float | None = None,
              request: dict | None = None, result: dict | None = None):
        """Emit a structured TraceLog via the context and dispatch to collector."""
        trace_log = self._ctx.emit(event, duration_ms=duration_ms,
                                   request=request, result=result)
        event_collector.emit_trace(trace_log)

    def attach(self, session: AgentSession):
        """Register all event handlers on the AgentSession."""
        self._ctx.new_turn(self._turn_index)

        self._emit("session.start", result={
            "room_name": self._room_name,
            "user_id": self._user_id,
            "agent_id": self._agent_id,
        })

        @session.on("user_state_changed")
        def on_user_state(ev):
            new_state = str(ev.new_state)
            old_state = str(ev.old_state)

            if new_state == "speaking":
                self._ctx.turn_start = time.time()
                self._emit("vad.speech_start")
                self._audio_recorder.start_user_turn(self._turn_index)

            elif old_state == "speaking":
                now = time.time()
                self._ctx.vad_end = now
                vad_dur = (now - self._ctx.turn_start) * 1000 if self._ctx.turn_start else 0
                self._emit("vad.speech_end", duration_ms=round(vad_dur, 1))

        @session.on("user_input_transcribed")
        def on_asr(ev):
            if ev.is_final:
                now = time.time()
                self._ctx.asr_final = now
                asr_latency = (now - self._ctx.vad_end) * 1000 if self._ctx.vad_end else 0

                self._emit("asr.end", duration_ms=round(asr_latency, 1), result={
                    "transcript": ev.transcript,
                    "language": ev.language or "",
                })

                # Emit composite user turn
                vad_dur = (self._ctx.vad_end - self._ctx.turn_start) * 1000 if self._ctx.turn_start else 0
                self._emit("turn.user_complete", result={
                    "turn_index": self._turn_index,
                    "transcript": ev.transcript,
                    "vad_duration_ms": round(vad_dur, 1),
                    "asr_latency_ms": round(asr_latency, 1),
                })

                # End user audio turn
                user_audio = self._audio_recorder.end_user_turn()

                # Enqueue user Message
                from backend.tracing.batch_writer import batch_writer
                batch_writer.enqueue_message({
                    "id": str(uuid.uuid4()),
                    "conversation_id": self._conversation_id,
                    "role": "user",
                    "content": ev.transcript,
                    "turn_index": self._turn_index,
                    "started_at": datetime.fromtimestamp(self._ctx.turn_start) if self._ctx.turn_start else datetime.now(),
                    "ended_at": datetime.fromtimestamp(now),
                    "is_truncated": False,
                    "audio_url": user_audio,
                })

            else:
                self._emit("asr.change", result={
                    "transcript": ev.transcript,
                    "is_final": False,
                })

        @session.on("agent_state_changed")
        def on_agent_state(ev):
            old, new = str(ev.old_state), str(ev.new_state)

            if new == "thinking":
                self._ctx.nlp_start = time.time()
                self._ctx.nlp_content_tokens = 0
                self._ctx.nlp_total_chunks = 0
                self._nlp_text = ""
                self._tool_calls = []
                # nlp.start is emitted by InstrumentedLLM.chat() with ctx size info

            elif new == "speaking" and old == "thinking":
                nlp_dur = (time.time() - self._ctx.nlp_start) * 1000 if self._ctx.nlp_start else 0
                self._ctx.tts_start = time.time()

                self._emit("nlp.end", duration_ms=round(nlp_dur, 1), result={
                    "token_count": self._ctx.nlp_content_tokens,
                    "total_chunks": self._ctx.nlp_total_chunks,
                    "ctx_messages": self._ctx.ctx_messages,
                    "ctx_tokens_est": self._ctx.ctx_tokens_est,
                })

                self._emit("tts.start")
                self._audio_recorder.start_agent_turn(self._turn_index)

            elif new == "listening" and old == "speaking":
                now = time.time()
                tts_dur = (now - self._ctx.tts_start) * 1000 if self._ctx.tts_start else 0
                e2e_dur = (now - self._ctx.turn_start) * 1000 if self._ctx.turn_start else 0

                # Compute TTFB/TTF10T relative to nlp_start
                ttfb_ms = None
                if self._ctx.nlp_ttfb and self._ctx.nlp_start:
                    ttfb_ms = round((self._ctx.nlp_ttfb - self._ctx.nlp_start) * 1000, 1)
                ttf10t_ms = None
                if self._ctx.nlp_ttf10t and self._ctx.nlp_start:
                    ttf10t_ms = round((self._ctx.nlp_ttf10t - self._ctx.nlp_start) * 1000, 1)

                self._emit("tts.end", duration_ms=round(tts_dur, 1), result={
                    "text": self._nlp_text[:200],
                })

                # Emit composite agent turn with all timing
                self._emit("turn.agent_complete", result={
                    "turn_index": self._turn_index,
                    "nlp_ttfb_ms": ttfb_ms,
                    "nlp_ttf10t_ms": ttf10t_ms,
                    "nlp_total_ms": round((self._ctx.tts_start - self._ctx.nlp_start) * 1000, 1) if self._ctx.tts_start and self._ctx.nlp_start else None,
                    "nlp_result": self._nlp_text[:500],
                    "token_count": self._ctx.nlp_content_tokens,
                    "ctx_messages": self._ctx.ctx_messages,
                    "ctx_tokens_est": self._ctx.ctx_tokens_est,
                    "tts_first_audio_ms": round((self._ctx.tts_first_audio - self._ctx.tts_start) * 1000, 1) if self._ctx.tts_first_audio and self._ctx.tts_start else None,
                    "tts_total_ms": round(tts_dur, 1),
                    "e2e_ms": round(e2e_dur, 1),
                    "tool_calls": [t.model_dump() for t in self._tool_calls],
                })

                # End agent audio turn
                agent_audio_url = self._audio_recorder.end_agent_turn()
                if agent_audio_url:
                    self._agent_audio_urls[self._turn_index] = agent_audio_url

                # Enqueue assistant Message
                from backend.tracing.batch_writer import batch_writer
                batch_writer.enqueue_message({
                    "id": str(uuid.uuid4()),
                    "conversation_id": self._conversation_id,
                    "role": "assistant",
                    "content": self._nlp_text,
                    "turn_index": self._turn_index,
                    "started_at": datetime.fromtimestamp(self._ctx.nlp_start) if self._ctx.nlp_start else datetime.now(),
                    "ended_at": datetime.now(),
                    "is_truncated": False,
                    "audio_url": agent_audio_url,
                })

                # Advance turn
                self._turn_index += 1
                self._ctx.new_turn(self._turn_index)

        @session.on("speech_created")
        def on_speech(ev):
            self._emit("nlp.speech_created", result={"source": str(ev.source)})

        @session.on("conversation_item_added")
        def on_item(ev):
            item = ev.item
            role = getattr(item, "role", "unknown")
            text = ""
            if hasattr(item, "text_content"):
                text = item.text_content or ""
            elif hasattr(item, "content"):
                for part in (item.content or []):
                    if hasattr(part, "text"):
                        text = part.text or ""
                        break

            if role == "assistant":
                self._nlp_text = text

        @session.on("overlapping_speech")
        def on_overlap(ev):
            spoken = self._nlp_text[:200] if self._nlp_text else ""
            cut = self._nlp_text[len(spoken):] if len(self._nlp_text) > 200 else ""
            position_ms = (ev.detected_at - self._session_start) * 1000

            self._emit("pipeline.interruption", result={
                "position_ms": round(position_ms, 1),
                "agent_text_spoken": spoken,
                "agent_text_cut": cut,
                "is_interruption": ev.is_interruption,
                "probability": round(ev.probability, 3),
                "detection_delay_ms": round(ev.detection_delay * 1000, 1),
            })

        @session.on("agent_false_interruption")
        def on_false_interrupt(ev):
            self._emit("pipeline.interruption_resume", result={
                "resumed": ev.resumed,
            })

        @session.on("error")
        def on_error(ev):
            self._emit("error", result={
                "source": str(ev.source),
                "message": str(ev.error),
            })

    # --- Audio recording ---

    @property
    def audio_recorder(self) -> AudioRecorder:
        return self._audio_recorder

    def push_user_audio(self, frame):
        """Called by the worker's audio stream loop to feed user audio frames."""
        self._audio_recorder.push_user_audio(frame)

    def push_agent_audio(self, frame):
        """Called by InstrumentedTTS to feed agent TTS audio frames."""
        self._audio_recorder.push_agent_audio(frame)

    # --- Tool & Memory recording methods ---

    def record_tool_call(self, tool_name: str, params: dict, result: str, duration_ms: float, success: bool):
        """Record a tool call for tracing."""
        tool_data = ToolCallData(
            tool_name=tool_name,
            params=params,
            result=str(result)[:200],
            duration_ms=duration_ms,
            call_time=time.time(),
        )
        self._tool_calls.append(tool_data)

        self._emit("nlp.tool_call", duration_ms=round(duration_ms, 1), request={
            "tool_name": tool_name,
            "params": params,
        }, result={
            "success": success,
            "result": str(result)[:200],
        })

    def record_tool_call_done(self):
        """Called after tool execution, before next LLM invocation.
        Advances sentence_id for multi-round tool calling tracking."""
        self._ctx.next_sentence()

    def record_memory_query(self, facts_count: int, vectors_count: int):
        self._emit("memory.query", result={
            "facts_count": facts_count,
            "vectors_count": vectors_count,
        })

    def record_hangup(self, consecutive_goodbyes: int, recent_turns: list[dict]):
        """Record hangup detection event — LLM determined conversation should end."""
        self._emit("hangup.detected", result={
            "consecutive_goodbyes": consecutive_goodbyes,
            "recent_turns": recent_turns,
            "turn_index": self._turn_index,
        })

    def record_memory_save(self, segments_count: int, facts_count: int):
        self._emit("memory.update", result={
            "segments_count": segments_count,
            "facts_count": facts_count,
        })

    # --- Legacy compatibility for InstrumentedLLM/TTS ---
    # These are no longer called — InstrumentedLLM/TTS now use TraceContext directly.
    # Kept as stubs in case any external code still calls them.

    def record_nlp_first_token(self):
        pass

    def record_nlp_token(self):
        pass

    def record_tts_first_audio(self):
        pass

    async def finalize(self):
        """Called when session ends. Emit SESSION_END, update Conversation."""
        total_dur = (time.time() - self._session_start) * 1000
        self._emit("session.end", duration_ms=round(total_dur, 1), result={
            "room_name": self._room_name,
            "user_id": self._user_id,
            "agent_id": self._agent_id,
            "total_duration_ms": round(total_dur, 1),
            "total_turns": self._turn_index,
        })

        # Update Conversation.ended_at
        try:
            from sqlalchemy import update
            from backend.db.engine import async_session
            from backend.db.models import Conversation

            async with async_session() as db:
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == self._conversation_id)
                    .values(ended_at=datetime.utcnow())
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to update conversation: {e}")

        # Save to long-term memory
        try:
            from backend.memory.manager import memory_manager
            from sqlalchemy import select
            from backend.db.engine import async_session
            from backend.db.models import Message

            async with async_session() as db:
                result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == self._conversation_id)
                    .order_by(Message.started_at)
                )
                messages = [
                    {"role": m.role, "content": m.content}
                    for m in result.scalars().all()
                ]

            if messages:
                await memory_manager.process_conversation(
                    user_id=self._user_id,
                    conversation_id=self._conversation_id,
                    messages=messages,
                )
                logger.info(f"[MEMORY][SAVE] user={self._user_id} messages={len(messages)}")
        except Exception as e:
            logger.warning(f"[MEMORY][SAVE] Failed: {e}")

        # Finalize audio recording
        full_audio_url = self._audio_recorder.finalize()
        if full_audio_url:
            logger.info(f"[AUDIO][FULL] room={self._room_name} path={full_audio_url}")

        # Final flush of batch writer
        from backend.tracing.batch_writer import batch_writer
        await batch_writer.stop()
