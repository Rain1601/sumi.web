"""LiveKit Agents v1.5 worker.

Uses the unified provider factory for pluggable ASR/NLP/TTS.
"""

import logging

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import silero

from backend.config import settings
from backend.providers.factory import create_stt, create_llm, create_tts, has_builtin_vad

logger = logging.getLogger(__name__)


async def resolve_model(model_id: str | None) -> dict | None:
    if not model_id:
        return None
    from sqlalchemy import select
    from backend.db.engine import async_session
    from backend.db.models import ProviderModel

    async with async_session() as session:
        result = await session.execute(select(ProviderModel).where(ProviderModel.id == model_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {"provider_name": row.provider_name, "model_name": row.model_name, "config": row.config or {}}


def setup_logging(session: AgentSession, room_name: str):
    """Structured pipeline event logging with timestamps for latency monitoring."""
    import time
    _timers: dict[str, float] = {}

    def _ts():
        return time.strftime("%H:%M:%S", time.localtime())

    @session.on("user_state_changed")
    def on_user_state(ev):
        if str(ev.new_state) == "speaking":
            _timers["vad_start"] = time.time()
            logger.info(f"[{_ts()}][VAD  ][START  ] room={room_name}")
        elif str(ev.old_state) == "speaking":
            dur = (time.time() - _timers.get("vad_start", time.time())) * 1000
            _timers["vad_end"] = time.time()
            logger.info(f"[{_ts()}][VAD  ][END    ] room={room_name} speech_dur={dur:.0f}ms")

    @session.on("user_input_transcribed")
    def on_asr(ev):
        if ev.is_final:
            asr_dur = (time.time() - _timers.get("vad_end", time.time())) * 1000
            _timers["asr_end"] = time.time()
            logger.info(f"[{_ts()}][ASR  ][FINAL  ] room={room_name} text=\"{ev.transcript}\" lang={ev.language} latency={asr_dur:.0f}ms")
        else:
            logger.info(f"[{_ts()}][ASR  ][PARTIAL] room={room_name} text=\"{ev.transcript}\"")

    @session.on("agent_state_changed")
    def on_state(ev):
        old, new = str(ev.old_state), str(ev.new_state)
        extra = ""
        if new == "thinking":
            _timers["nlp_start"] = time.time()
        elif new == "speaking" and old == "thinking":
            nlp_dur = (time.time() - _timers.get("nlp_start", time.time())) * 1000
            _timers["tts_start"] = time.time()
            extra = f" nlp_latency={nlp_dur:.0f}ms"
        elif new == "listening" and old == "speaking":
            tts_dur = (time.time() - _timers.get("tts_start", time.time())) * 1000
            e2e_dur = (time.time() - _timers.get("vad_start", time.time())) * 1000
            extra = f" tts_dur={tts_dur:.0f}ms e2e={e2e_dur:.0f}ms"
        logger.info(f"[{_ts()}][STATE][{old:8s}-> {new:8s}] room={room_name}{extra}")

    @session.on("speech_created")
    def on_speech(ev):
        logger.info(f"[{_ts()}][NLP  ][SPEECH ] room={room_name} source={ev.source}")

    @session.on("conversation_item_added")
    def on_item(ev):
        item = ev.item
        role = getattr(item, "role", "unknown")
        text = ""
        if hasattr(item, "text_content"):
            text = item.text_content[:100] if item.text_content else ""
        elif hasattr(item, "content"):
            for part in (item.content or []):
                if hasattr(part, "text"):
                    text = part.text[:100]
                    break
        logger.info(f"[{_ts()}][TRANS][{role:8s}] room={room_name} text=\"{text}\"")

    @session.on("error")
    def on_error(ev):
        logger.error(f"[{_ts()}][ERROR][{ev.source}] room={room_name} error={ev.error}")


async def entrypoint(ctx: JobContext):
    logger.info(f"[WORKER] Joining room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    user_id = participant.identity
    agent_id = participant.metadata or "default"
    logger.info(f"[WORKER] Participant: user={user_id} agent={agent_id}")

    # Load agent from DB
    from backend.agents.manager import agent_manager
    try:
        agent_def = await agent_manager.load_agent(agent_id)
    except ValueError:
        logger.error(f"[WORKER] Agent '{agent_id}' not found")
        return

    # Resolve model IDs → model info dicts
    stt_info = await resolve_model(getattr(agent_def, "asr_model_id", None))
    llm_info = await resolve_model(getattr(agent_def, "nlp_model_id", None))
    tts_info = await resolve_model(getattr(agent_def, "tts_model_id", None))

    logger.info(f"[WORKER] Models: ASR={stt_info and stt_info['model_name']} "
                f"NLP={llm_info and llm_info['model_name']} "
                f"TTS={tts_info and tts_info['model_name']}")

    # Create plugins via unified factory
    voiceprint_enabled = getattr(agent_def, "voiceprint_enabled", False)
    stt = create_stt(stt_info, voiceprint=voiceprint_enabled)
    llm = create_llm(llm_info)
    tts = create_tts(tts_info)

    # Give voiceprint STT access to room for data channel events
    if voiceprint_enabled and hasattr(stt, "set_room"):
        stt.set_room(ctx.room)

    # Agent with system prompt
    agent = Agent(instructions=agent_def.system_prompt or "You are a helpful voice assistant.")

    # Session — only use Silero VAD if STT doesn't have built-in VAD
    session_kwargs = dict(stt=stt, llm=llm, tts=tts, allow_interruptions=agent_def.interruption_policy != "never")

    if has_builtin_vad(stt_info):
        logger.info("[VAD] Disabled — STT has built-in VAD")
    else:
        session_kwargs["vad"] = silero.VAD.load(min_speech_duration=0.05, min_silence_duration=0.3)
        logger.info("[VAD] Using Silero VAD")

    session = AgentSession(**session_kwargs)
    setup_logging(session, ctx.room.name)

    logger.info("[WORKER] Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    logger.info(f"[WORKER] Session started for room={ctx.room.name}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
            agent_name="sumi-agent",   # Only accept dispatches for this name
            num_idle_processes=1,
            load_threshold=0.9,
        ),
    )
