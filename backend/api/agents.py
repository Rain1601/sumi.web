"""Agents CRUD API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.db.models import (
    Agent, AgentSkill, AgentTool, AgentVariable, ProviderModel, gen_uuid,
)

router = APIRouter()


class AgentResponse(BaseModel):
    id: str
    name_zh: str
    name_en: str
    description_zh: str | None
    description_en: str | None
    system_prompt: str
    asr_model_id: str | None
    tts_model_id: str | None
    nlp_model_id: str | None
    asr_model_name: str | None = None
    tts_model_name: str | None = None
    nlp_model_name: str | None = None
    vad_mode: str
    vad_config: dict | None
    tools: list[str]
    interruption_policy: str
    voiceprint_enabled: bool
    language: str
    is_active: bool
    opening_line: str | None = None
    user_prompt: str | None = None
    version: int = 1
    status: str = "draft"
    folder_id: str | None = None
    call_control: dict | None = None
    cloned_from: str | None = None


class AgentCreate(BaseModel):
    name_zh: str
    name_en: str
    description_zh: str | None = None
    description_en: str | None = None
    system_prompt: str = ""
    asr_model_id: str | None = None
    tts_model_id: str | None = None
    nlp_model_id: str | None = None
    vad_mode: str = "backend"
    vad_config: dict | None = None
    tools: list[str] = []
    interruption_policy: str = "always"
    voiceprint_enabled: bool = False
    language: str = "auto"
    opening_line: str | None = None
    user_prompt: str | None = None
    status: str = "draft"
    folder_id: str | None = None
    call_control: dict | None = None


class AgentUpdate(BaseModel):
    name_zh: str | None = None
    name_en: str | None = None
    description_zh: str | None = None
    description_en: str | None = None
    system_prompt: str | None = None
    asr_model_id: str | None = None
    tts_model_id: str | None = None
    nlp_model_id: str | None = None
    vad_mode: str | None = None
    vad_config: dict | None = None
    tools: list[str] | None = None
    interruption_policy: str | None = None
    voiceprint_enabled: bool | None = None
    language: str | None = None
    is_active: bool | None = None
    opening_line: str | None = None
    user_prompt: str | None = None
    status: str | None = None
    folder_id: str | None = None
    call_control: dict | None = None


async def _to_response(agent: Agent, db) -> AgentResponse:
    """Convert Agent ORM to response, resolving model names."""
    asr_name = tts_name = nlp_name = None

    model_ids = [mid for mid in [agent.asr_model_id, agent.tts_model_id, agent.nlp_model_id] if mid]
    if model_ids:
        result = await db.execute(select(ProviderModel).where(ProviderModel.id.in_(model_ids)))
        models_map = {m.id: m.name for m in result.scalars().all()}
        asr_name = models_map.get(agent.asr_model_id)
        tts_name = models_map.get(agent.tts_model_id)
        nlp_name = models_map.get(agent.nlp_model_id)

    return AgentResponse(
        id=agent.id,
        name_zh=agent.name_zh,
        name_en=agent.name_en,
        description_zh=agent.description_zh,
        description_en=agent.description_en,
        system_prompt=agent.system_prompt,
        asr_model_id=agent.asr_model_id,
        tts_model_id=agent.tts_model_id,
        nlp_model_id=agent.nlp_model_id,
        asr_model_name=asr_name,
        tts_model_name=tts_name,
        nlp_model_name=nlp_name,
        vad_mode=agent.vad_mode,
        vad_config=agent.vad_config,
        tools=agent.tools or [],
        interruption_policy=agent.interruption_policy,
        voiceprint_enabled=agent.voiceprint_enabled,
        language=agent.language,
        is_active=agent.is_active,
        opening_line=agent.opening_line,
        user_prompt=agent.user_prompt,
        version=agent.version,
        status=agent.status,
        folder_id=agent.folder_id,
        call_control=agent.call_control,
        cloned_from=agent.cloned_from,
    )


@router.get("/", response_model=list[AgentResponse])
async def list_agents(db: DbSession):
    """List all agents."""
    result = await db.execute(select(Agent).order_by(Agent.created_at))
    agents = result.scalars().all()
    return [await _to_response(a, db) for a in agents]


@router.post("/", response_model=AgentResponse)
async def create_agent(req: AgentCreate, db: DbSession):
    """Create a new agent."""
    # Resolve provider info from model IDs
    asr_provider = asr_config = ""
    tts_provider = tts_config = ""
    nlp_provider = nlp_config = ""

    for mid, ptype in [(req.asr_model_id, "asr"), (req.tts_model_id, "tts"), (req.nlp_model_id, "nlp")]:
        if mid:
            r = await db.execute(select(ProviderModel).where(ProviderModel.id == mid))
            pm = r.scalar_one_or_none()
            if not pm:
                raise HTTPException(400, f"{ptype} model '{mid}' not found")
            if pm.provider_type != ptype:
                raise HTTPException(400, f"Model '{mid}' is type '{pm.provider_type}', expected '{ptype}'")

    agent = Agent(
        id=gen_uuid(),
        name_zh=req.name_zh,
        name_en=req.name_en,
        description_zh=req.description_zh,
        description_en=req.description_en,
        system_prompt=req.system_prompt,
        asr_model_id=req.asr_model_id,
        tts_model_id=req.tts_model_id,
        nlp_model_id=req.nlp_model_id,
        asr_provider="",
        asr_config={},
        tts_provider="",
        tts_config={},
        nlp_provider="",
        nlp_config={},
        vad_mode=req.vad_mode,
        vad_config=req.vad_config,
        tools=req.tools,
        interruption_policy=req.interruption_policy,
        voiceprint_enabled=req.voiceprint_enabled,
        language=req.language,
        opening_line=req.opening_line,
        user_prompt=req.user_prompt,
        status=req.status,
        folder_id=req.folder_id,
        call_control=req.call_control,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return await _to_response(agent, db)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: DbSession):
    """Get a specific agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return await _to_response(agent, db)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, req: AgentUpdate, db: DbSession):
    """Update an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    for field in ["name_zh", "name_en", "description_zh", "description_en", "system_prompt",
                  "asr_model_id", "tts_model_id", "nlp_model_id",
                  "vad_mode", "vad_config", "tools", "interruption_policy",
                  "voiceprint_enabled", "language", "is_active",
                  "opening_line", "user_prompt", "status", "folder_id", "call_control"]:
        value = getattr(req, field)
        if value is not None:
            setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return await _to_response(agent, db)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, db: DbSession):
    """Delete an agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"ok": True}


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
async def duplicate_agent(agent_id: str, db: DbSession):
    """Duplicate an agent with all its config."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Agent not found")

    new_id = gen_uuid()
    clone = Agent(
        id=new_id,
        name_zh=f"{original.name_zh} (Copy)",
        name_en=f"{original.name_en} (Copy)",
        description_zh=original.description_zh,
        description_en=original.description_en,
        system_prompt=original.system_prompt,
        asr_model_id=original.asr_model_id,
        tts_model_id=original.tts_model_id,
        nlp_model_id=original.nlp_model_id,
        asr_provider=original.asr_provider,
        asr_config=original.asr_config,
        tts_provider=original.tts_provider,
        tts_config=original.tts_config,
        nlp_provider=original.nlp_provider,
        nlp_config=original.nlp_config,
        vad_mode=original.vad_mode,
        vad_config=original.vad_config,
        tools=original.tools,
        interruption_policy=original.interruption_policy,
        voiceprint_enabled=original.voiceprint_enabled,
        language=original.language,
        opening_line=original.opening_line,
        user_prompt=original.user_prompt,
        version=1,
        status="draft",
        folder_id=original.folder_id,
        call_control=original.call_control,
        cloned_from=agent_id,
    )
    db.add(clone)

    # Copy variables
    vars_result = await db.execute(
        select(AgentVariable).where(AgentVariable.agent_id == agent_id)
    )
    for v in vars_result.scalars().all():
        db.add(AgentVariable(
            id=gen_uuid(), agent_id=new_id, name=v.name, code=v.code,
            var_type=v.var_type, default_value=v.default_value, description=v.description,
        ))

    # Copy skills
    skills_result = await db.execute(
        select(AgentSkill).where(AgentSkill.agent_id == agent_id)
    )
    for s in skills_result.scalars().all():
        db.add(AgentSkill(
            id=gen_uuid(), agent_id=new_id, name=s.name, code=s.code,
            description=s.description, content=s.content, sort_order=s.sort_order,
        ))

    # Copy tools
    tools_result = await db.execute(
        select(AgentTool).where(AgentTool.agent_id == agent_id)
    )
    for t in tools_result.scalars().all():
        db.add(AgentTool(
            id=gen_uuid(), agent_id=new_id, name=t.name, tool_id=t.tool_id,
            description=t.description, parameters_schema=t.parameters_schema,
            execution_type=t.execution_type,
        ))

    await db.commit()
    await db.refresh(clone)
    return await _to_response(clone, db)


@router.post("/{agent_id}/publish", response_model=AgentResponse)
async def publish_agent(agent_id: str, db: DbSession):
    """Promote agent from draft to published, increment version."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    agent.status = "published"
    agent.version = agent.version + 1
    await db.commit()
    await db.refresh(agent)
    return await _to_response(agent, db)
