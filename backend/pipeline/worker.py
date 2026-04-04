"""LiveKit Agents v1.5 worker.

Uses the unified provider factory for pluggable ASR/NLP/TTS.
"""

import logging
import uuid

from sqlalchemy import select

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents import llm as lk_llm
from livekit.plugins import silero

from backend.config import settings
from backend.db.engine import async_session
from backend.db.models import (
    AgentSkill,
    AgentTool,
    AgentVariable,
    Conversation,
    ProviderModel,
)
from backend.providers.factory import create_stt, create_llm, create_tts, has_builtin_vad

logger = logging.getLogger(__name__)


def substitute_vars(text: str, variables: dict[str, str]) -> str:
    """Replace ${code} placeholders with variable values."""
    for code, value in variables.items():
        text = text.replace(f"${{{code}}}", value)
    return text


def _make_tool_callable(
    tool_record: AgentTool,
    user_id: str,
    conversation_id: str,
    agent_id: str,
):
    """Create a dynamic async callable for an AgentTool.

    Each tool gets its own closure so the captured name/context is correct.
    Executes through the BaseTool.execute() chain for real tool invocation.
    """
    import time
    from backend.agents.tools.registry import tool_registry
    from backend.agents.tools.base import ToolContext

    tool_name = tool_record.tool_id
    tool_description = tool_record.description or tool_record.name

    @lk_llm.function_tool(name=tool_name, description=tool_description)
    async def _tool_fn(**kwargs):
        tool = tool_registry.get(tool_name)
        if tool:
            context = ToolContext(
                user_id=user_id,
                conversation_id=conversation_id,
                agent_id=agent_id,
            )
            t0 = time.monotonic()
            result = await tool.execute(kwargs, context)
            dur_ms = round((time.monotonic() - t0) * 1000)
            logger.info(
                f"[TOOL][CALL] {tool_name} dur={dur_ms}ms success={result.success}"
            )
            return result.output
        else:
            logger.warning(f"[TOOL] Tool '{tool_name}' not found in registry")
            return f"Tool {tool_name} not found"

    return _tool_fn


async def resolve_model(model_id: str | None) -> dict | None:
    if not model_id:
        return None

    async with async_session() as session:
        result = await session.execute(select(ProviderModel).where(ProviderModel.id == model_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {"provider_name": row.provider_name, "model_name": row.model_name, "config": row.config or {}}


async def _load_agent_extras(agent_id: str) -> tuple[dict[str, str], list, list]:
    """Load variables, skills, and tools for an agent from the DB.

    Returns (variables_dict, skills_list, tools_list).
    """
    async with async_session() as db:
        var_result = await db.execute(
            select(AgentVariable).where(AgentVariable.agent_id == agent_id)
        )
        variables = {v.code: v.default_value or "" for v in var_result.scalars().all()}

        skill_result = await db.execute(
            select(AgentSkill)
            .where(AgentSkill.agent_id == agent_id)
            .order_by(AgentSkill.sort_order)
        )
        skills = list(skill_result.scalars().all())

        tool_result = await db.execute(
            select(AgentTool).where(AgentTool.agent_id == agent_id)
        )
        tools = list(tool_result.scalars().all())

    return variables, skills, tools


def _build_system_prompt(
    agent_def,
    variables: dict[str, str],
    skills: list,
) -> str:
    """Build final system prompt with variable substitution and skills."""
    parts = []

    # 1. Goal
    if agent_def.goal:
        parts.append(f"## 你的任务目标\n{agent_def.goal}")

    # 2. System prompt
    prompt = substitute_vars(
        agent_def.system_prompt or "You are a helpful voice assistant.",
        variables,
    )
    parts.append(prompt)

    # 3. User prompt
    if agent_def.user_prompt:
        parts.append(substitute_vars(agent_def.user_prompt, variables))

    # 4. Skills
    if skills:
        skills_text = "\n## 对话技能/话术"
        for s in skills:
            skills_text += f"\n### {s.name} (code: {s.code})"
            if s.description:
                skills_text += f"\n{s.description}"
            if s.content:
                skills_text += f"\n{s.content}"
            skills_text += f"\n当你进入此阶段时，在回复末尾添加 <skill>{s.code}</skill>"
        parts.append(skills_text)

    return "\n\n".join(parts)


def _build_tools(agent_tools: list) -> list:
    """Create LiveKit FunctionTool instances from AgentTool DB records."""
    lk_tools = []
    for t in agent_tools:
        lk_tools.append(_make_tool_callable(t.tool_id, t.description or t.name))
    return lk_tools


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
    async with async_session() as db:
        conv = Conversation(id=conversation_id, user_id=user_id, agent_id=agent_id, room_name=ctx.room.name)
        db.add(conv)
        await db.commit()
    logger.info(f"[WORKER] Conversation created: {conversation_id}")

    # Load agent definition from DB
    from backend.agents.manager import agent_manager
    try:
        agent_def = await agent_manager.load_agent(agent_id)
    except ValueError:
        logger.error(f"[WORKER] Agent '{agent_id}' not found")
        return

    # Load agent extras: variables, skills, tools
    variables, skills, agent_tools = await _load_agent_extras(agent_id)
    logger.info(
        f"[WORKER] Loaded extras: {len(variables)} variables, "
        f"{len(skills)} skills, {len(agent_tools)} tools"
    )

    # Build system prompt with variable substitution and skills
    system_prompt = _build_system_prompt(agent_def, variables, skills)

    # Inject memory context into system prompt
    from backend.memory.manager import memory_manager
    try:
        memory_context = await memory_manager.build_context(user_id)
        if memory_context:
            system_prompt += "\n\n## 用户记忆\n" + memory_context
            logger.info(f"[MEMORY][QUERY  ] user={user_id} context_len={len(memory_context)}")
    except Exception as e:
        logger.warning(f"[MEMORY][QUERY  ] Failed: {e}")

    # Build function-calling tools
    lk_tools = _build_tools(agent_tools) if agent_tools else None

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

    # Create session tracer early so instrumented wrappers can use it
    from backend.tracing.session_tracer import SessionTracer
    tracer = SessionTracer(
        conversation_id=conversation_id,
        room_name=ctx.room.name,
        user_id=user_id,
        agent_id=agent_id,
    )

    # Wrap LLM and TTS with instrumentation for token/audio timing
    from backend.tracing.instrumented_llm import InstrumentedLLM
    from backend.tracing.instrumented_tts import InstrumentedTTS
    llm = InstrumentedLLM(llm, tracer)
    tts = InstrumentedTTS(tts, tracer)

    # Agent with system prompt and tools
    agent = Agent(
        instructions=system_prompt,
        tools=lk_tools,
    )

    # Session — only use Silero VAD if STT doesn't have built-in VAD
    session_kwargs = dict(stt=stt, llm=llm, tts=tts, allow_interruptions=agent_def.interruption_policy != "never")

    if has_builtin_vad(stt_info):
        logger.info("[VAD] Disabled — STT has built-in VAD")
    else:
        session_kwargs["vad"] = silero.VAD.load(min_speech_duration=0.05, min_silence_duration=0.3)
        logger.info("[VAD] Using Silero VAD")

    session = AgentSession(**session_kwargs)

    # Attach session tracer event handlers to the session
    tracer.attach(session)

    logger.info("[WORKER] Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    logger.info(f"[WORKER] Session started for room={ctx.room.name}")

    # Speak the opening line if configured
    if agent_def.opening_line:
        await session.say(agent_def.opening_line)
        logger.info(f"[WORKER] Opening line sent: {agent_def.opening_line[:50]}")

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
