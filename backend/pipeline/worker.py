"""LiveKit Agents v1.5 worker.

Uses the unified provider factory for pluggable ASR/NLP/TTS.
"""

import logging
import uuid

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


async def entrypoint(ctx: JobContext):
    logger.info(f"[WORKER] Joining room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Start batch writer + wire to event collector (worker is a separate process)
    from backend.tracing.batch_writer import batch_writer
    from backend.tracing.collector import event_collector
    await batch_writer.start()
    event_collector.set_batch_writer(batch_writer)

    participant = await ctx.wait_for_participant()
    user_id = participant.identity
    agent_id = participant.metadata or "default"
    logger.info(f"[WORKER] Participant: user={user_id} agent={agent_id}")

    # Create conversation record
    conversation_id = str(uuid.uuid4())
    from backend.db.engine import async_session
    from backend.db.models import Conversation
    async with async_session() as db:
        conv = Conversation(id=conversation_id, user_id=user_id, agent_id=agent_id, room_name=ctx.room.name)
        db.add(conv)
        await db.commit()
    logger.info(f"[WORKER] Conversation created: {conversation_id}")

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

    # Attach session tracer for structured event collection
    from backend.tracing.session_tracer import SessionTracer
    tracer = SessionTracer(
        conversation_id=conversation_id,
        room_name=ctx.room.name,
        user_id=user_id,
        agent_id=agent_id,
    )
    tracer.attach(session)

    logger.info("[WORKER] Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    logger.info(f"[WORKER] Session started for room={ctx.room.name}")

    # Wait until session ends (room closes or participant leaves)
    # The entrypoint function stays alive as long as the job is active.
    # LiveKit Agents framework keeps it running until the job is done.
    # Register shutdown hook to finalize tracing.
    ctx.add_shutdown_callback(tracer.finalize)


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
