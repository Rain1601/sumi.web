"""Agent Tools CRUD API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.db.models import Agent, AgentTool, gen_uuid

router = APIRouter()


class ToolCreate(BaseModel):
    name: str
    tool_id: str
    description: str | None = None
    parameters_schema: dict | None = None
    execution_type: str = "sync_round"


class ToolUpdate(BaseModel):
    name: str | None = None
    tool_id: str | None = None
    description: str | None = None
    parameters_schema: dict | None = None
    execution_type: str | None = None


class ToolResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    tool_id: str
    description: str | None
    parameters_schema: dict | None
    execution_type: str


async def _get_agent_or_404(agent_id: str, db) -> Agent:
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.get("/{agent_id}/tools", response_model=list[ToolResponse])
async def list_tools(agent_id: str, db: DbSession):
    """List all tools for an agent."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentTool).where(AgentTool.agent_id == agent_id)
    )
    return [
        ToolResponse(
            id=t.id, agent_id=t.agent_id, name=t.name, tool_id=t.tool_id,
            description=t.description, parameters_schema=t.parameters_schema,
            execution_type=t.execution_type,
        )
        for t in result.scalars().all()
    ]


@router.post("/{agent_id}/tools", response_model=ToolResponse)
async def create_tool(agent_id: str, req: ToolCreate, db: DbSession):
    """Create a new tool config for an agent."""
    await _get_agent_or_404(agent_id, db)
    tool = AgentTool(
        id=gen_uuid(),
        agent_id=agent_id,
        name=req.name,
        tool_id=req.tool_id,
        description=req.description,
        parameters_schema=req.parameters_schema,
        execution_type=req.execution_type,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return ToolResponse(
        id=tool.id, agent_id=tool.agent_id, name=tool.name, tool_id=tool.tool_id,
        description=tool.description, parameters_schema=tool.parameters_schema,
        execution_type=tool.execution_type,
    )


@router.patch("/{agent_id}/tools/{tool_config_id}", response_model=ToolResponse)
async def update_tool(agent_id: str, tool_config_id: str, req: ToolUpdate, db: DbSession):
    """Update an agent tool config."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentTool).where(AgentTool.id == tool_config_id, AgentTool.agent_id == agent_id)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(404, "Tool not found")

    for field in ["name", "tool_id", "description", "parameters_schema", "execution_type"]:
        value = getattr(req, field)
        if value is not None:
            setattr(tool, field, value)

    await db.commit()
    await db.refresh(tool)
    return ToolResponse(
        id=tool.id, agent_id=tool.agent_id, name=tool.name, tool_id=tool.tool_id,
        description=tool.description, parameters_schema=tool.parameters_schema,
        execution_type=tool.execution_type,
    )


@router.delete("/{agent_id}/tools/{tool_config_id}")
async def delete_tool(agent_id: str, tool_config_id: str, db: DbSession):
    """Delete an agent tool config."""
    await _get_agent_or_404(agent_id, db)
    result = await db.execute(
        select(AgentTool).where(AgentTool.id == tool_config_id, AgentTool.agent_id == agent_id)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(404, "Tool not found")
    await db.delete(tool)
    await db.commit()
    return {"ok": True}
