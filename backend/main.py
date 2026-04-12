from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.engine import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if "sqlite" in settings.database_url:
        settings.db_path.mkdir(parents=True, exist_ok=True)
    await init_db()

    # Auto-seed: ensure default-tenant has template agents/models
    from backend.db.seed import seed
    await seed(skip_init=True)

    # Register providers and tools
    from backend.providers.registry import register_default_providers
    from backend.agents.tools.common.datetime_tool import DateTimeTool
    from backend.agents.tools.common.weather import WeatherTool
    from backend.agents.tools.common.web_search import WebSearchTool
    from backend.agents.tools.registry import tool_registry

    register_default_providers()
    tool_registry.register(DateTimeTool())
    tool_registry.register(WeatherTool())
    tool_registry.register(WebSearchTool())

    # Wire up tracing
    from backend.tracing.collector import event_collector
    from backend.tracing.broadcaster import trace_broadcaster
    from backend.tracing.batch_writer import batch_writer
    event_collector.set_broadcaster(trace_broadcaster)
    event_collector.set_batch_writer(batch_writer)

    yield
    # Shutdown


app = FastAPI(
    title="Kodama",
    description="Real-time Voice AI Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/api/admin/debug/tenants")
async def debug_tenants():
    """Debug: show all tenants and their agent counts."""
    from sqlalchemy import select, func
    from backend.db.engine import async_session
    from backend.db.models import Agent, TenantMember, Tenant

    async with async_session() as db:
        result = await db.execute(select(TenantMember))
        members = result.scalars().all()

        tenants = []
        for m in members:
            count = await db.execute(
                select(func.count()).select_from(Agent).where(Agent.tenant_id == m.tenant_id)
            )
            tenants.append({
                "tenant_id": m.tenant_id,
                "user_id": m.user_id,
                "role": m.role,
                "agent_count": count.scalar() or 0,
            })
    return {"tenants": tenants}


@app.post("/api/admin/seed")
async def admin_seed():
    """One-time seed: populate default-tenant with template agents and models.
    Then clone to all existing user tenants that have no agents yet."""
    from backend.db.seed import seed
    await seed(skip_init=True)

    from sqlalchemy import select, func, update
    from backend.db.engine import async_session
    from backend.db.models import Agent, ProviderModel, TenantMember
    from backend.api.deps import _clone_default_data, SYSTEM_TENANT_ID

    # Fix TTS configs: update CosyVoice models to v3-flash and fix voice names
    async with async_session() as db:
        # Update model entries to use v3-flash
        await db.execute(
            update(ProviderModel)
            .where(ProviderModel.provider_name == "dashscope", ProviderModel.provider_type == "tts")
            .values(model_name="cosyvoice-v3-flash")
        )
        # Fix legacy tts_config: add _v3 suffix if missing
        result = await db.execute(select(Agent).where(Agent.tts_provider == "dashscope"))
        for agent in result.scalars().all():
            voice = (agent.tts_config or {}).get("voice", "longanyang")
            # Add _v3 suffix if not a standard v3 voice
            if voice not in ("longanyang", "longanhuan") and not voice.endswith("_v3"):
                voice = voice + "_v3"
            agent.tts_config = {"voice": voice}
        await db.commit()
    tts_msg = "TTS configs updated to v3 voices"

    # Clone to tenants with no agents
    cloned_count = 0
    async with async_session() as db:
        result = await db.execute(
            select(TenantMember).where(TenantMember.role == "owner")
        )
        for m in result.scalars().all():
            if m.tenant_id == SYSTEM_TENANT_ID:
                continue
            count = await db.execute(
                select(func.count()).select_from(Agent).where(Agent.tenant_id == m.tenant_id)
            )
            if (count.scalar() or 0) == 0:
                await _clone_default_data(m.tenant_id, m.user_id, db)
                cloned_count += 1
        await db.commit()

    return {"status": "ok", "message": f"Seed complete. {tts_msg}. Cloned to {cloned_count} new tenants."}


# Register routers
from backend.api import auth, agents, agent_variables, agent_skills, agent_tools, agent_audio_init, agent_conversation_test, agent_voice_test, annotations, conversations, memory, models, rooms, traces  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["rooms"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(agent_variables.router, prefix="/api/agents", tags=["agent-variables"])
app.include_router(agent_skills.router, prefix="/api/agents", tags=["agent-skills"])
app.include_router(agent_tools.router, prefix="/api/agents", tags=["agent-tools"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(traces.router, prefix="/api/traces", tags=["traces"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])
app.include_router(agent_audio_init.router, prefix="/api/agents", tags=["agent-audio-init"])
app.include_router(agent_conversation_test.router, prefix="/api/agents", tags=["agent-conversation-test"])
app.include_router(agent_voice_test.router, prefix="/api/agents", tags=["agent-voice-test"])

# Serve recorded audio files
from pathlib import Path as _Path
_audio_dir = _Path(__file__).resolve().parent.parent / "data" / "audio"
_audio_dir.mkdir(parents=True, exist_ok=True)
(_audio_dir / "init").mkdir(exist_ok=True)

from fastapi.staticfiles import StaticFiles
app.mount("/api/audio", StaticFiles(directory=str(_audio_dir)), name="audio")
