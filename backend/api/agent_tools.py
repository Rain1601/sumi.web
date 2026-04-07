"""Agent Tools CRUD API."""

import time
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import Auth, DbSession
from backend.db.models import Agent, AgentTool, gen_uuid

logger = logging.getLogger(__name__)

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
async def list_tools(agent_id: str, auth: Auth, db: DbSession):
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
async def create_tool(agent_id: str, req: ToolCreate, auth: Auth, db: DbSession):
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
async def update_tool(agent_id: str, tool_config_id: str, req: ToolUpdate, auth: Auth, db: DbSession):
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
async def delete_tool(agent_id: str, tool_config_id: str, auth: Auth, db: DbSession):
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


# ─── Tool Execution (Test/Run) ──────────────────────────────────

class ToolRunRequest(BaseModel):
    params: dict = {}


class ToolRunResponse(BaseModel):
    success: bool
    output: str
    data: dict = {}
    duration_ms: float


@router.post("/run/{tool_id}", response_model=ToolRunResponse)
async def run_tool(tool_id: str, req: ToolRunRequest, auth: Auth):
    """Execute a tool directly for testing. No agent context required."""
    from backend.agents.tools.registry import tool_registry
    from backend.agents.tools.base import ToolContext

    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(404, f"Tool '{tool_id}' not found in registry")

    context = ToolContext(
        user_id="test_user",
        conversation_id="test",
        agent_id="test",
    )

    t0 = time.monotonic()
    try:
        result = await tool.execute(req.params, context)
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        raise HTTPException(500, f"Tool execution failed: {str(e)[:200]}")

    duration_ms = round((time.monotonic() - t0) * 1000, 1)

    return ToolRunResponse(
        success=result.success,
        output=result.output,
        data=result.data,
        duration_ms=duration_ms,
    )
