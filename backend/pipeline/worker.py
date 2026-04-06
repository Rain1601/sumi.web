"""LiveKit Agents v1.5 worker.

Uses the unified provider factory for pluggable ASR/NLP/TTS.
"""

import asyncio
import logging
import uuid

from sqlalchemy import select

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents import llm as lk_llm
from livekit.plugins import silero

from backend.config import settings
from backend.db.engine import async_session
from backend.pipeline.hangup_detector import HangupDetector
from backend.db.models import (
    AgentRule,
    AgentSkill,
    AgentTool,
    AgentVariable,
    Conversation,
    ProviderModel,
)
from backend.pipeline.prompt_builder import build_dynamic_prompt, format_rules, format_optimization
from backend.pipeline.task_chain import TaskChainController
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

    LiveKit Agents introspects function signatures via inspect.signature() and
    typing.get_type_hints() to build Pydantic models for the OpenAI function-
    calling schema.  A plain **kwargs function causes KeyError because there are
    no type hints to look up.  We therefore dynamically build an async function
    whose parameter names, types, defaults, and descriptions match the tool's
    JSON Schema — exactly what LiveKit expects.
    """
    import time
    import textwrap
    from typing import Annotated
    from pydantic import Field
    from backend.agents.tools.registry import tool_registry
    from backend.agents.tools.base import ToolContext

    tool_name = tool_record.tool_id
    tool_description = tool_record.description or tool_record.name

    tool_impl = tool_registry.get(tool_name)
    if not tool_impl:
        logger.warning(f"[TOOL] Tool '{tool_name}' not in registry — skipping")
        return None

    # --- Build typed parameters from JSON Schema -------------------------
    schema = tool_impl.parameters
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))

    _TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }

    # Build annotations & defaults dicts consumed by exec'd function
    annotations: dict = {}
    defaults: dict = {}

    for prop_name, prop_info in properties.items():
        py_type = _TYPE_MAP.get(prop_info.get("type", "string"), str)
        desc = prop_info.get("description", "")
        default = prop_info.get("default")

        if prop_name in required_set:
            annotations[prop_name] = Annotated[py_type, Field(description=desc)]
        else:
            annotations[prop_name] = Annotated[py_type, Field(description=desc, default=default or "")]
            defaults[prop_name] = default or ""

    # --- Build the actual async function via exec so it has real params ---
    param_names = list(properties.keys())
    sig_parts = []
    for p in param_names:
        if p in defaults:
            sig_parts.append(f"{p}={p!r}" if isinstance(defaults[p], str) else f"{p}={defaults[p]!r}")
        else:
            sig_parts.append(p)
    sig_str = ", ".join(sig_parts)

    func_code = textwrap.dedent(f"""\
        async def _tool_fn({sig_str}):
            _params = {{}}
            for _n in _param_names:
                _params[_n] = locals()[_n]
            return await _execute(_params)
    """)

    # Closure that does the real work — avoids putting complex logic in exec
    async def _execute(params: dict) -> str:
        context = ToolContext(
            user_id=user_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )
        t0 = time.monotonic()
        result = await tool_impl.execute(params, context)
        dur_ms = round((time.monotonic() - t0) * 1000)
        logger.info(f"[TOOL][CALL] {tool_name} dur={dur_ms}ms success={result.success}")
        return result.output

    ns: dict = {"_execute": _execute, "_param_names": param_names}
    exec(func_code, ns)  # noqa: S102
    fn = ns["_tool_fn"]

    # Attach annotations so get_type_hints() works
    fn.__annotations__ = annotations
    fn.__module__ = __name__

    # Decorate with LiveKit function_tool
    return lk_llm.function_tool(name=tool_name, description=tool_description)(fn)


async def resolve_model(model_id: str | None) -> dict | None:
    if not model_id:
        return None

    async with async_session() as session:
        result = await session.execute(select(ProviderModel).where(ProviderModel.id == model_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        return {"provider_name": row.provider_name, "model_name": row.model_name, "config": row.config or {}}


async def _load_agent_extras(agent_id: str) -> tuple[dict[str, str], list, list, list]:
    """Load variables, skills, tools, and rules for an agent from the DB.

    Returns (variables_dict, skills_list, tools_list, rules_list).
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

        rule_result = await db.execute(
            select(AgentRule).where(AgentRule.agent_id == agent_id, AgentRule.is_active == True)
        )
        rules = [
            {"rule_type": r.rule_type, "content": r.content, "priority": r.priority, "is_active": r.is_active}
            for r in rule_result.scalars().all()
        ]

    return variables, skills, tools, rules


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


def _build_tools(
    agent_tools: list,
    user_id: str,
    conversation_id: str,
    agent_id: str,
) -> list:
    """Create LiveKit FunctionTool instances from AgentTool DB records."""
    lk_tools = []
    for t in agent_tools:
        fn = _make_tool_callable(t, user_id, conversation_id, agent_id)
        if fn is not None:
            lk_tools.append(fn)
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

    # Load agent extras: variables, skills, tools, rules
    variables, skills, agent_tools, rules = await _load_agent_extras(agent_id)
    logger.info(
        f"[WORKER] Loaded extras: {len(variables)} variables, "
        f"{len(skills)} skills, {len(agent_tools)} tools, {len(rules)} rules"
    )

    # Initialize task chain controller if configured
    task_chain_ctrl = None
    if agent_def.task_chain and agent_def.task_chain.get("tasks"):
        skills_map = {s.code: s for s in skills}
        task_chain_ctrl = TaskChainController(agent_def.task_chain, skills_map)
        logger.info(f"[WORKER] Task chain initialized: entry={task_chain_ctrl.current_task_id}")

    # Build system prompt — use 6-layer dynamic prompt if task chain or role is defined
    memory_prompt = ""
    from backend.memory.manager import memory_manager
    try:
        memory_context = await memory_manager.build_context(user_id)
        if memory_context:
            memory_prompt = "## 用户记忆\n" + memory_context
            logger.info(f"[MEMORY][QUERY  ] user={user_id} context_len={len(memory_context)}")
    except Exception as e:
        logger.warning(f"[MEMORY][QUERY  ] Failed: {e}")

    # Merge DB rules with inline rules from agent_def
    all_rules = rules + (agent_def.rules or [])

    if agent_def.role or task_chain_ctrl:
        # 6-layer dynamic prompt
        system_prompt = build_dynamic_prompt(
            role=substitute_vars(agent_def.role or "", variables),
            target=substitute_vars(agent_def.goal or "", variables),
            task_prompt=task_chain_ctrl.build_task_prompt() if task_chain_ctrl else "",
            rules_text=format_rules(all_rules),
            memory_prompt=memory_prompt,
            optimization=format_optimization(agent_def.optimization),
            system_prompt=substitute_vars(agent_def.system_prompt or "", variables),
        )
        # Append skills that aren't part of task chain
        if skills:
            non_chain_skills = [s for s in skills if not task_chain_ctrl or s.code != task_chain_ctrl.current_skill_code()]
            if non_chain_skills:
                skills_text = "\n\n## 对话技能/话术"
                for s in non_chain_skills:
                    skills_text += f"\n### {s.name} (code: {s.code})"
                    if s.description:
                        skills_text += f"\n{s.description}"
                    if s.content:
                        skills_text += f"\n{s.content}"
                system_prompt += skills_text
    else:
        # Legacy: _build_system_prompt for backward compatibility
        system_prompt = _build_system_prompt(agent_def, variables, skills)
        if all_rules:
            system_prompt += "\n\n" + format_rules(all_rules)
        if memory_prompt:
            system_prompt += "\n\n" + memory_prompt

    # Build function-calling tools
    lk_tools = _build_tools(agent_tools, user_id, conversation_id, agent_id) if agent_tools else None

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

    # Wrap LLM and TTS with instrumentation — pass TraceContext for structured logging
    from backend.tracing.instrumented_llm import InstrumentedLLM
    from backend.tracing.instrumented_tts import InstrumentedTTS
    llm = InstrumentedLLM(llm, tracer.ctx)
    tts = InstrumentedTTS(tts, tracer.ctx, audio_recorder=tracer.audio_recorder)

    # Agent with system prompt and tools
    agent = Agent(
        instructions=system_prompt,
        tools=lk_tools,
    )

    # Session with adaptive interruption detection
    allow_interrupts = agent_def.interruption_policy != "never"
    session_kwargs = dict(
        stt=stt,
        llm=llm,
        tts=tts,
        turn_handling={
            "interruption": {
                "enabled": allow_interrupts,
                "mode": "adaptive",              # ML-based: ignores backchannels like 嗯/哦
                "min_duration": 0.5,             # min 0.5s speech to trigger detection
                "resume_false_interruption": True,  # resume agent speech on false interrupts
                "false_interruption_timeout": 2.0,
            },
        },
    )

    if has_builtin_vad(stt_info):
        logger.info("[VAD] Skipped Silero — STT provider has built-in server-side VAD")
    else:
        session_kwargs["vad"] = silero.VAD.load(min_speech_duration=0.1, min_silence_duration=0.6)
        logger.info("[VAD] Using Silero VAD (speech≥0.1s, silence≥0.6s)")

    session = AgentSession(**session_kwargs)
    logger.info(f"[WORKER] Interruption: mode=adaptive enabled={allow_interrupts}")

    # Attach session tracer event handlers to the session
    tracer.attach(session)

    logger.info("[WORKER] Starting agent session...")
    await session.start(agent=agent, room=ctx.room)
    logger.info(f"[WORKER] Session started for room={ctx.room.name}")

    # --- Hangup detection: LLM-based async goodbye detection ---
    hangup = HangupDetector(threshold=2)

    @session.on("user_input_transcribed")
    def _hangup_on_user(ev):
        if ev.is_final and not hangup.should_hangup:
            hangup.feed_turn("user", ev.transcript)

    @session.on("agent_state_changed")
    def _hangup_on_agent_done(ev):
        old, new = str(ev.old_state), str(ev.new_state)
        # When agent finishes speaking → feed agent text for async LLM check
        if new == "listening" and old == "speaking" and not hangup.should_hangup:
            hangup.feed_turn("agent", tracer._nlp_text)

    async def _hangup_monitor():
        """Poll for LLM hangup decision and disconnect gracefully."""
        while not hangup.should_hangup:
            await asyncio.sleep(0.5)
        # Emit hangup trace event before disconnecting
        tracer.record_hangup(
            consecutive_goodbyes=hangup._consecutive_goodbyes,
            recent_turns=hangup._recent_turns[-4:],
        )
        # Brief pause to let final TTS finish playing
        await asyncio.sleep(1.5)
        logger.info(f"[HANGUP] Disconnecting room={ctx.room.name}")
        ctx.shutdown()

    asyncio.create_task(_hangup_monitor())

    # Speak the opening line if configured
    if agent_def.opening_line:
        await session.say(agent_def.opening_line)
        logger.info(f"[WORKER] Opening line sent: {agent_def.opening_line[:50]}")

    # Capture user audio for recording
    async def _capture_user_audio():
        try:
            from livekit import rtc
            audio_stream = rtc.AudioStream.from_participant(
                participant=participant,
                track_source=rtc.TrackSource.SOURCE_MICROPHONE,
                sample_rate=16000,
                num_channels=1,
            )
            async for ev in audio_stream:
                tracer.push_user_audio(ev.frame)
        except Exception as e:
            logger.warning(f"[AUDIO] User audio capture stopped: {e}")

    asyncio.create_task(_capture_user_audio())
    logger.info("[AUDIO] User audio capture started")

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
