"""Agent Variables CRUD API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import Auth, DbSession
from backend.db.models import Agent, AgentVariable, gen_uuid

router = APIRouter()


class VariableCreate(BaseModel):
    name: str
    code: str
    var_type: str = "string"
    default_value: str | None = None
    description: str | None = None


class VariableUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    var_type: str | None = None
    default_value: str | None = None
    description: str | None = None


class VariableResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    code: str
    var_type: str
    default_value: str | None
    description: str | None


async def _get_agent_or_404(agent_id: str, db) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.get("/{agent_id}/variables", response_model=list[VariableResponse])
async def list_variables(agent_id: str, auth: Auth, db: DbSession):
    """List all variables for an agent."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentVariable).where(AgentVariable.agent_id == agent_id)
    )
    return [
        VariableResponse(
            id=v.id, agent_id=v.agent_id, name=v.name, code=v.code,
            var_type=v.var_type, default_value=v.default_value, description=v.description,
        )
        for v in result.scalars().all()
    ]


@router.post("/{agent_id}/variables", response_model=VariableResponse)
async def create_variable(agent_id: str, req: VariableCreate, auth: Auth, db: DbSession):
    """Create a new variable for an agent."""
    await _get_agent_or_404(agent_id, db)
    var = AgentVariable(
        id=gen_uuid(),
        agent_id=agent_id,
        name=req.name,
        code=req.code,
        var_type=req.var_type,
        default_value=req.default_value,
        description=req.description,
    )
    db.add(var)
    await db.commit()
    await db.refresh(var)
    return VariableResponse(
        id=var.id, agent_id=var.agent_id, name=var.name, code=var.code,
        var_type=var.var_type, default_value=var.default_value, description=var.description,
    )


@router.patch("/{agent_id}/variables/{var_id}", response_model=VariableResponse)
async def update_variable(agent_id: str, var_id: str, req: VariableUpdate, auth: Auth, db: DbSession):
    """Update an agent variable."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentVariable).where(AgentVariable.id == var_id, AgentVariable.agent_id == agent_id)
    )
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(404, "Variable not found")

    for field in ["name", "code", "var_type", "default_value", "description"]:
        value = getattr(req, field)
        if value is not None:
            setattr(var, field, value)

    await db.commit()
    await db.refresh(var)
    return VariableResponse(
        id=var.id, agent_id=var.agent_id, name=var.name, code=var.code,
        var_type=var.var_type, default_value=var.default_value, description=var.description,
    )


@router.delete("/{agent_id}/variables/{var_id}")
async def delete_variable(agent_id: str, var_id: str, auth: Auth, db: DbSession):
    """Delete an agent variable."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentVariable).where(AgentVariable.id == var_id, AgentVariable.agent_id == agent_id)
    )
    var = result.scalar_one_or_none()
    if not var:
        raise HTTPException(404, "Variable not found")
    await db.delete(var)
    await db.commit()
    return {"ok": True}
