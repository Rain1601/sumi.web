"""Agent Skills CRUD API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.db.models import Agent, AgentSkill, gen_uuid

router = APIRouter()


class SkillCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    content: str | None = None
    skill_type: str = "free"
    qa_pairs: dict | None = None
    logic_tree: dict | None = None
    entry_prompt: str | None = None
    exit_conditions: dict | None = None
    sort_order: int = 0


class SkillUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    content: str | None = None
    skill_type: str | None = None
    qa_pairs: dict | None = None
    logic_tree: dict | None = None
    entry_prompt: str | None = None
    exit_conditions: dict | None = None
    sort_order: int | None = None


class SkillResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    code: str
    description: str | None
    content: str | None
    skill_type: str = "free"
    qa_pairs: dict | None = None
    logic_tree: dict | None = None
    entry_prompt: str | None = None
    exit_conditions: dict | None = None
    sort_order: int


async def _get_agent_or_404(agent_id: str, db) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.get("/{agent_id}/skills", response_model=list[SkillResponse])
async def list_skills(agent_id: str, db: DbSession):
    """List all skills for an agent."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentSkill)
        .where(AgentSkill.agent_id == agent_id)
        .order_by(AgentSkill.sort_order)
    )
    return [
        SkillResponse(
            id=s.id, agent_id=s.agent_id, name=s.name, code=s.code,
            description=s.description, content=s.content,
            skill_type=s.skill_type, qa_pairs=s.qa_pairs, logic_tree=s.logic_tree,
            entry_prompt=s.entry_prompt, exit_conditions=s.exit_conditions,
            sort_order=s.sort_order,
        )
        for s in result.scalars().all()
    ]


@router.post("/{agent_id}/skills", response_model=SkillResponse)
async def create_skill(agent_id: str, req: SkillCreate, db: DbSession):
    """Create a new skill for an agent."""
    await _get_agent_or_404(agent_id, db)
    skill = AgentSkill(
        id=gen_uuid(),
        agent_id=agent_id,
        name=req.name,
        code=req.code,
        description=req.description,
        content=req.content,
        skill_type=req.skill_type,
        qa_pairs=req.qa_pairs,
        logic_tree=req.logic_tree,
        entry_prompt=req.entry_prompt,
        exit_conditions=req.exit_conditions,
        sort_order=req.sort_order,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return SkillResponse(
        id=skill.id, agent_id=skill.agent_id, name=skill.name, code=skill.code,
        description=skill.description, content=skill.content, sort_order=skill.sort_order,
    )


@router.patch("/{agent_id}/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(agent_id: str, skill_id: str, req: SkillUpdate, db: DbSession):
    """Update an agent skill."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id, AgentSkill.agent_id == agent_id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(404, "Skill not found")

    for field in ["name", "code", "description", "content", "skill_type",
                  "qa_pairs", "logic_tree", "entry_prompt", "exit_conditions", "sort_order"]:
        value = getattr(req, field)
        if value is not None:
            setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return SkillResponse(
        id=skill.id, agent_id=skill.agent_id, name=skill.name, code=skill.code,
        description=skill.description, content=skill.content, sort_order=skill.sort_order,
    )


@router.delete("/{agent_id}/skills/{skill_id}")
async def delete_skill(agent_id: str, skill_id: str, db: DbSession):
    """Delete an agent skill."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id, AgentSkill.agent_id == agent_id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(404, "Skill not found")
    await db.delete(skill)
    await db.commit()
    return {"ok": True}
