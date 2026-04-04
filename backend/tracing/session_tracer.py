import logging
import time
import uuid
from datetime import datetime
from typing import Any

from livekit.agents.voice import AgentSession

from backend.pipeline.events import PipelineEventType
from backend.tracing.collector import event_collector
from backend.tracing.schemas import (
    VadData, AsrData, NlpData, TtsData, ToolCallData,
    InterruptionData, ErrorData, SessionData,
    UserTurnData, AgentTurnData,
)

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

        # Per-turn timing state
        self._t: dict[str, float] = {}
        self._nlp_token_count = 0
        self._nlp_text = ""
        self._agent_spoken_text = ""
        self._tool_calls: list[ToolCallData] = []

    def _ts(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime())

    def _emit(self, event_type: PipelineEventType, data: Any = None, duration_ms: float | None = None):
        payload = data.model_dump() if hasattr(data, "model_dump") else (data or {})
        event_collector.emit(
            conversation_id=self._conversation_id,
            event_type=event_type,
            data=payload,
            duration_ms=duration_ms,
        )

    def attach(self, session: AgentSession):
        """Register all event handlers on the AgentSession."""
        self._emit(PipelineEventType.SESSION_START, SessionData(
            room_name=self._room_name, user_id=self._user_id, agent_id=self._agent_id,
        ))
        logger.info(f"[{self._ts()}][SESSION][START] room={self._room_name} user={self._user_id} agent={self._agent_id}")

        @session.on("user_state_changed")
        def on_user_state(ev):
            new_state = str(ev.new_state)
            old_state = str(ev.old_state)

            if new_state == "speaking":
                self._t["vad_start"] = time.time()
                self._emit(PipelineEventType.VAD_SPEECH_START)
                logger.info(f"[{self._ts()}][VAD  ][START  ] room={self._room_name}")

            elif old_state == "speaking":
                vad_dur = (time.time() - self._t.get("vad_start", time.time())) * 1000
                self._t["vad_end"] = time.time()
                self._emit(PipelineEventType.VAD_SPEECH_END, VadData(duration_ms=vad_dur), duration_ms=vad_dur)
                logger.info(f"[{self._ts()}][VAD  ][END    ] room={self._room_name} speech_dur={vad_dur:.0f}ms")

        @session.on("user_input_transcribed")
        def on_asr(ev):
            if ev.is_final:
                asr_final = time.time()
                asr_latency = (asr_final - self._t.get("vad_end", asr_final)) * 1000
                self._t["asr_final"] = asr_final

                asr_data = AsrData(
                    transcript=ev.transcript,
                    language=ev.language or "",
                    is_final=True,
                    latency_ms=asr_latency,
                )
                self._emit(PipelineEventType.ASR_END, asr_data, duration_ms=asr_latency)
                logger.info(f"[{self._ts()}][ASR  ][FINAL  ] room={self._room_name} text=\"{ev.transcript}\" latency={asr_latency:.0f}ms")

                # Emit composite USER_TURN_COMPLETE
                vad_dur = (self._t.get("vad_end", asr_final) - self._t.get("vad_start", asr_final)) * 1000
                user_turn = UserTurnData(
                    turn_index=self._turn_index,
                    user_speech_start_time=self._t.get("vad_start", 0),
                    vad_duration_ms=vad_dur,
                    asr_final_time=asr_final,
                    asr_result=ev.transcript,
                    asr_latency_ms=asr_latency,
                )
                self._emit(PipelineEventType.USER_TURN_COMPLETE, user_turn)

                # Enqueue user Message
                from backend.tracing.batch_writer import batch_writer
                batch_writer.enqueue_message({
                    "id": str(uuid.uuid4()),
                    "conversation_id": self._conversation_id,
                    "role": "user",
                    "content": ev.transcript,
                    "turn_index": self._turn_index,
                    "started_at": datetime.fromtimestamp(self._t.get("vad_start", asr_final)),
                    "ended_at": datetime.fromtimestamp(asr_final),
                    "is_truncated": False,
                })

            else:
                self._emit(PipelineEventType.ASR_CHANGE, AsrData(
                    transcript=ev.transcript, is_final=False,
                ))
                logger.info(f"[{self._ts()}][ASR  ][PARTIAL] room={self._room_name} text=\"{ev.transcript}\"")

        @session.on("agent_state_changed")
        def on_agent_state(ev):
            old, new = str(ev.old_state), str(ev.new_state)
            extra = ""

            if new == "thinking":
                self._t["nlp_start"] = time.time()
                self._nlp_token_count = 0
                self._nlp_text = ""
                self._tool_calls = []
                self._emit(PipelineEventType.NLP_START)

            elif new == "speaking" and old == "thinking":
                nlp_dur = (time.time() - self._t.get("nlp_start", time.time())) * 1000
                self._t["tts_start"] = time.time()
                self._emit(PipelineEventType.TTS_START)
                extra = f" nlp_latency={nlp_dur:.0f}ms"

            elif new == "listening" and old == "speaking":
                tts_dur = (time.time() - self._t.get("tts_start", time.time())) * 1000
                e2e_dur = (time.time() - self._t.get("vad_start", time.time())) * 1000
                extra = f" tts_dur={tts_dur:.0f}ms e2e={e2e_dur:.0f}ms"

                self._emit(PipelineEventType.TTS_END, TtsData(
                    text=self._nlp_text[:200],
                    total_ms=tts_dur,
                ), duration_ms=tts_dur)

                # Emit composite AGENT_TURN_COMPLETE
                nlp_total = (self._t.get("tts_start", 0) - self._t.get("nlp_start", 0)) * 1000 if self._t.get("nlp_start") else None
                agent_turn = AgentTurnData(
                    turn_index=self._turn_index,
                    nlp_request_time=self._t.get("nlp_start", 0),
                    nlp_ttfb_ms=self._t.get("nlp_ttfb"),
                    nlp_ttf10t_ms=self._t.get("nlp_ttf10t"),
                    nlp_complete_time=self._t.get("tts_start", 0),
                    nlp_result=self._nlp_text[:500],
                    tts_start_time=self._t.get("tts_start", 0),
                    tts_first_audio_time=self._t.get("tts_first_audio"),
                    tts_end_time=time.time(),
                    tool_calls=self._tool_calls,
                )
                self._emit(PipelineEventType.AGENT_TURN_COMPLETE, agent_turn)

                # Enqueue assistant Message
                from backend.tracing.batch_writer import batch_writer
                batch_writer.enqueue_message({
                    "id": str(uuid.uuid4()),
                    "conversation_id": self._conversation_id,
                    "role": "assistant",
                    "content": self._nlp_text,
                    "turn_index": self._turn_index,
                    "started_at": datetime.fromtimestamp(self._t.get("nlp_start", time.time())),
                    "ended_at": datetime.now(),
                    "is_truncated": False,
                })

                self._turn_index += 1

            logger.info(f"[{self._ts()}][STATE][{old:8s}-> {new:8s}] room={self._room_name}{extra}")

        @session.on("speech_created")
        def on_speech(ev):
            self._emit(PipelineEventType.NLP_CHUNK, NlpData(text="", model=""))
            logger.info(f"[{self._ts()}][NLP  ][SPEECH ] room={self._room_name} source={ev.source}")

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

            logger.info(f"[{self._ts()}][TRANS][{role:8s}] room={self._room_name} text=\"{text[:100]}\"")

        @session.on("error")
        def on_error(ev):
            self._emit(PipelineEventType.ERROR, ErrorData(source=str(ev.source), message=str(ev.error)))
            logger.error(f"[{self._ts()}][ERROR][{ev.source}] room={self._room_name} error={ev.error}")

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

        self._emit(PipelineEventType.NLP_TOOL_CALL, tool_data)
        logger.info(
            f"[{self._ts()}][TOOL ][{'OK' if success else 'FAIL':7s}] "
            f"room={self._room_name} tool={tool_name} dur={duration_ms:.0f}ms "
            f"result=\"{str(result)[:60]}\""
        )

    def record_memory_query(self, facts_count: int, vectors_count: int):
        self._emit(PipelineEventType.MEMORY_QUERY, {
            "facts_count": facts_count,
            "vectors_count": vectors_count,
        })
        logger.info(f"[{self._ts()}][MEMORY][QUERY  ] room={self._room_name} facts={facts_count} vectors={vectors_count}")

    def record_memory_save(self, segments_count: int, facts_count: int):
        self._emit(PipelineEventType.MEMORY_UPDATE, {
            "segments_count": segments_count,
            "facts_count": facts_count,
        })
        logger.info(f"[{self._ts()}][MEMORY][SAVE   ] room={self._room_name} segments={segments_count} facts={facts_count}")

    # --- Methods called by InstrumentedLLM/TTS ---

    def record_nlp_first_token(self):
        """Called by InstrumentedLLM when first token arrives."""
        ttfb = (time.time() - self._t.get("nlp_start", time.time())) * 1000
        self._t["nlp_ttfb"] = ttfb
        self._emit(PipelineEventType.NLP_FIRST_TOKEN, NlpData(ttfb_ms=ttfb))
        logger.info(f"[{self._ts()}][NLP  ][TTFB   ] room={self._room_name} ttfb={ttfb:.0f}ms")

    def record_nlp_token(self):
        """Called by InstrumentedLLM on each token."""
        self._nlp_token_count += 1
        if self._nlp_token_count == 10:
            ttf10t = (time.time() - self._t.get("nlp_start", time.time())) * 1000
            self._t["nlp_ttf10t"] = ttf10t
            logger.info(f"[{self._ts()}][NLP  ][TTF10T ] room={self._room_name} ttf10t={ttf10t:.0f}ms")

    def record_tts_first_audio(self):
        """Called by InstrumentedTTS when first audio frame is produced."""
        self._t["tts_first_audio"] = time.time()
        fa_ms = (time.time() - self._t.get("tts_start", time.time())) * 1000
        self._emit(PipelineEventType.TTS_FIRST_AUDIO, TtsData(first_audio_ms=fa_ms))
        logger.info(f"[{self._ts()}][TTS  ][FIRST  ] room={self._room_name} first_audio={fa_ms:.0f}ms")

    async def finalize(self):
        """Called when session ends. Emit SESSION_END, update Conversation."""
        total_dur = (time.time() - self._session_start) * 1000
        self._emit(PipelineEventType.SESSION_END, SessionData(
            room_name=self._room_name, user_id=self._user_id, agent_id=self._agent_id,
            total_duration_ms=total_dur,
        ), duration_ms=total_dur)
        logger.info(f"[{self._ts()}][SESSION][END] room={self._room_name} duration={total_dur:.0f}ms")

        # Update Conversation.ended_at
        try:
            from sqlalchemy import update
            from backend.db.engine import async_session
            from backend.db.models import Conversation
            from datetime import datetime

            async with async_session() as db:
                await db.execute(
                    update(Conversation)
                    .where(Conversation.id == self._conversation_id)
                    .values(ended_at=datetime.utcnow())
                )
                await db.commit()
        except Exception as e:
            logger.error(f"[SESSION] Failed to update conversation: {e}")

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
                logger.info(f"[{self._ts()}][MEMORY][SAVE   ] user={self._user_id} messages={len(messages)}")
        except Exception as e:
            logger.warning(f"[MEMORY][SAVE   ] Failed: {e}")

        # Final flush of batch writer
        from backend.tracing.batch_writer import batch_writer
        await batch_writer.stop()
