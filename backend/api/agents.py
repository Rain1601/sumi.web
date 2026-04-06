"""Agents CRUD API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.db.models import (
    Agent, AgentRule, AgentSkill, AgentTool, AgentVariable, AgentVersion, ProviderModel, gen_uuid,
)

router = APIRouter()


class AgentResponse(BaseModel):
    id: str
    name_zh: str
    name_en: str
    description_zh: str | None
    description_en: str | None
    system_prompt: str
    goal: str | None = None
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
    role: str | None = None
    task_chain: dict | None = None
    rules: list | None = None
    optimization: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AgentCreate(BaseModel):
    name_zh: str
    name_en: str
    description_zh: str | None = None
    description_en: str | None = None
    system_prompt: str = ""
    goal: str | None = None
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
    role: str | None = None
    task_chain: dict | None = None
    rules: list | None = None
    optimization: dict | None = None


class AgentUpdate(BaseModel):
    name_zh: str | None = None
    name_en: str | None = None
    description_zh: str | None = None
    description_en: str | None = None
    system_prompt: str | None = None
    goal: str | None = None
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
    role: str | None = None
    task_chain: dict | None = None
    rules: list | None = None
    optimization: dict | None = None


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
        goal=agent.goal,
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
        role=agent.role,
        task_chain=agent.task_chain,
        rules=agent.rules,
        optimization=agent.optimization,
        created_at=agent.created_at.isoformat() if agent.created_at else None,
        updated_at=agent.updated_at.isoformat() if agent.updated_at else None,
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
        goal=req.goal,
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
        role=req.role,
        task_chain=req.task_chain,
        rules=req.rules,
        optimization=req.optimization,
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

    for field in ["name_zh", "name_en", "description_zh", "description_en", "system_prompt", "goal",
                  "asr_model_id", "tts_model_id", "nlp_model_id",
                  "vad_mode", "vad_config", "tools", "interruption_policy",
                  "voiceprint_enabled", "language", "is_active",
                  "opening_line", "user_prompt", "status", "folder_id", "call_control",
                  "role", "task_chain", "rules", "optimization"]:
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
        goal=original.goal,
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
        role=original.role,
        task_chain=original.task_chain,
        rules=original.rules,
        optimization=original.optimization,
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
            description=s.description, content=s.content,
            skill_type=s.skill_type, qa_pairs=s.qa_pairs, logic_tree=s.logic_tree,
            entry_prompt=s.entry_prompt, exit_conditions=s.exit_conditions,
            sort_order=s.sort_order,
        ))

    # Copy rules
    rules_result = await db.execute(
        select(AgentRule).where(AgentRule.agent_id == agent_id)
    )
    for r in rules_result.scalars().all():
        db.add(AgentRule(
            id=gen_uuid(), agent_id=new_id, rule_type=r.rule_type,
            content=r.content, priority=r.priority, is_active=r.is_active,
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


def _snapshot_agent(agent: Agent) -> dict:
    """Create a JSON-serializable snapshot of agent config."""
    return {
        "name_zh": agent.name_zh,
        "name_en": agent.name_en,
        "description_zh": agent.description_zh,
        "description_en": agent.description_en,
        "system_prompt": agent.system_prompt,
        "goal": agent.goal,
        "asr_model_id": agent.asr_model_id,
        "tts_model_id": agent.tts_model_id,
        "nlp_model_id": agent.nlp_model_id,
        "vad_mode": agent.vad_mode,
        "vad_config": agent.vad_config,
        "tools": agent.tools,
        "interruption_policy": agent.interruption_policy,
        "voiceprint_enabled": agent.voiceprint_enabled,
        "language": agent.language,
        "opening_line": agent.opening_line,
        "user_prompt": agent.user_prompt,
        "call_control": agent.call_control,
        "role": agent.role,
        "task_chain": agent.task_chain,
        "rules": agent.rules,
        "optimization": agent.optimization,
    }


class PublishRequest(BaseModel):
    change_summary: str | None = None


@router.post("/{agent_id}/publish", response_model=AgentResponse)
async def publish_agent(agent_id: str, db: DbSession, req: PublishRequest | None = None):
    """Promote agent from draft to published, increment version, snapshot config."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    new_version = agent.version + 1

    # Snapshot current config before publish
    version_record = AgentVersion(
        id=gen_uuid(),
        agent_id=agent_id,
        version=new_version,
        snapshot=_snapshot_agent(agent),
        change_summary=req.change_summary if req else None,
    )
    db.add(version_record)

    agent.status = "published"
    agent.version = new_version
    await db.commit()
    await db.refresh(agent)
    return await _to_response(agent, db)


# --- Agent Versions ---

class VersionResponse(BaseModel):
    id: str
    agent_id: str
    version: int
    change_summary: str | None
    published_by: str | None
    created_at: str | None


@router.get("/{agent_id}/versions", response_model=list[VersionResponse])
async def list_versions(agent_id: str, db: DbSession):
    """List all published versions of an agent."""
    result = await db.execute(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.version.desc())
    )
    return [
        VersionResponse(
            id=v.id, agent_id=v.agent_id, version=v.version,
            change_summary=v.change_summary, published_by=v.published_by,
            created_at=v.created_at.isoformat() if v.created_at else None,
        )
        for v in result.scalars().all()
    ]


@router.get("/{agent_id}/versions/{version_id}", response_model=dict)
async def get_version(agent_id: str, version_id: str, db: DbSession):
    """Get the full snapshot of a specific version."""
    result = await db.execute(
        select(AgentVersion).where(AgentVersion.id == version_id, AgentVersion.agent_id == agent_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Version not found")
    return {
        "id": v.id,
        "agent_id": v.agent_id,
        "version": v.version,
        "snapshot": v.snapshot,
        "change_summary": v.change_summary,
        "published_by": v.published_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/{agent_id}/versions/{version_id}/rollback", response_model=AgentResponse)
async def rollback_to_version(agent_id: str, version_id: str, db: DbSession):
    """Rollback agent to a previous version's config. Creates a new draft."""
    result = await db.execute(
        select(AgentVersion).where(AgentVersion.id == version_id, AgentVersion.agent_id == agent_id)
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(404, "Version not found")

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Apply snapshot fields to agent
    snap = v.snapshot
    for field in ["name_zh", "name_en", "description_zh", "description_en", "system_prompt",
                  "goal", "asr_model_id", "tts_model_id", "nlp_model_id",
                  "vad_mode", "vad_config", "tools", "interruption_policy",
                  "voiceprint_enabled", "language", "opening_line", "user_prompt",
                  "call_control", "role", "task_chain", "rules", "optimization"]:
        if field in snap:
            setattr(agent, field, snap[field])

    agent.status = "draft"  # Rollback creates a draft that needs re-publishing
    await db.commit()
    await db.refresh(agent)
    return await _to_response(agent, db)


# --- Agent Rules CRUD ---

class RuleResponse(BaseModel):
    id: str
    agent_id: str
    rule_type: str
    content: str
    priority: int
    is_active: bool


class RuleCreate(BaseModel):
    rule_type: str  # "forbidden" | "required" | "format"
    content: str
    priority: int = 0
    is_active: bool = True


class RuleUpdate(BaseModel):
    rule_type: str | None = None
    content: str | None = None
    priority: int | None = None
    is_active: bool | None = None


@router.get("/{agent_id}/rules", response_model=list[RuleResponse])
async def list_rules(agent_id: str, db: DbSession):
    result = await db.execute(
        select(AgentRule).where(AgentRule.agent_id == agent_id).order_by(AgentRule.priority.desc())
    )
    return [RuleResponse(id=r.id, agent_id=r.agent_id, rule_type=r.rule_type,
                         content=r.content, priority=r.priority, is_active=r.is_active)
            for r in result.scalars().all()]


@router.post("/{agent_id}/rules", response_model=RuleResponse)
async def create_rule(agent_id: str, req: RuleCreate, db: DbSession):
    rule = AgentRule(
        id=gen_uuid(), agent_id=agent_id,
        rule_type=req.rule_type, content=req.content,
        priority=req.priority, is_active=req.is_active,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return RuleResponse(id=rule.id, agent_id=rule.agent_id, rule_type=rule.rule_type,
                        content=rule.content, priority=rule.priority, is_active=rule.is_active)


@router.patch("/{agent_id}/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(agent_id: str, rule_id: str, req: RuleUpdate, db: DbSession):
    result = await db.execute(
        select(AgentRule).where(AgentRule.id == rule_id, AgentRule.agent_id == agent_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    for field in ["rule_type", "content", "priority", "is_active"]:
        value = getattr(req, field)
        if value is not None:
            setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return RuleResponse(id=rule.id, agent_id=rule.agent_id, rule_type=rule.rule_type,
                        content=rule.content, priority=rule.priority, is_active=rule.is_active)


@router.delete("/{agent_id}/rules/{rule_id}")
async def delete_rule(agent_id: str, rule_id: str, db: DbSession):
    result = await db.execute(
        select(AgentRule).where(AgentRule.id == rule_id, AgentRule.agent_id == agent_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"ok": True}
