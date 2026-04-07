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


@app.post("/api/admin/seed")
async def admin_seed():
    """One-time seed: populate default-tenant with template agents and models.
    Then clone to all existing user tenants that have no agents yet."""
    from backend.db.seed import seed
    await seed(skip_init=True)

    # Clone to existing tenants that have 0 agents
    from sqlalchemy import select, func
    from backend.db.engine import async_session
    from backend.db.models import Agent, Tenant, TenantMember
    from backend.api.deps import _clone_default_data, SYSTEM_TENANT_ID

    # Count system templates
    async with async_session() as db:
        sys_count_result = await db.execute(
            select(func.count()).select_from(Agent).where(Agent.tenant_id == SYSTEM_TENANT_ID)
        )
        sys_agent_count = sys_count_result.scalar() or 0

    cloned_count = 0
    async with async_session() as db:
        # Find all personal tenants (not the system tenant)
        result = await db.execute(
            select(TenantMember).where(TenantMember.role == "owner")
        )
        members = result.scalars().all()

        for m in members:
            if m.tenant_id == SYSTEM_TENANT_ID:
                continue
            # Clone if tenant has fewer agents than system templates
            count = await db.execute(
                select(func.count()).select_from(Agent).where(Agent.tenant_id == m.tenant_id)
            )
            tenant_count = count.scalar() or 0
            if tenant_count < sys_agent_count:
                # Delete old agents + models, then re-clone fresh
                from backend.db.models import ProviderModel as PM
                await db.execute(Agent.__table__.delete().where(Agent.tenant_id == m.tenant_id))
                await db.execute(PM.__table__.delete().where(PM.tenant_id == m.tenant_id))
                await _clone_default_data(m.tenant_id, m.user_id, db)
                cloned_count += 1

        await db.commit()

    return {"status": "ok", "message": f"Seed complete. Cloned to {cloned_count} existing tenants ({sys_agent_count} templates)."}


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
