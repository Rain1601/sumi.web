"""Agent Conversation Test API — run NLP adversarial dialogue test via SSE."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.api.deps import DbSession
from backend.config import settings
from backend.db.models import Agent, AgentRule
from backend.pipeline.prompt_builder import build_dynamic_prompt, format_rules
from backend.services.conversation_test import run_conversation_test

router = APIRouter()


class ConversationTestRequest(BaseModel):
    scenario: str = Field(..., description="测试场景描述")
    persona: str = Field("", description="模拟用户人设（留空自动生成）")
    max_turns: int = Field(10, ge=2, le=30, description="最大对话回合数")
    evaluate: bool = Field(True, description="是否在对话结束后评估")
    model: str = Field("claude-sonnet-4-20250514", description="LLM 模型")


@router.post("/{agent_id}/conversation-test")
async def run_agent_conversation_test(
    agent_id: str,
    request: ConversationTestRequest,
    db: DbSession,
):
    """Run an NLP adversarial conversation test for an agent, streamed via SSE."""

    # Load agent with rules
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Load rules
    rules_result = await db.execute(
        select(AgentRule).where(AgentRule.agent_id == agent_id)
    )
    rules = rules_result.scalars().all()

    # Build the full runtime prompt
    rules_text = format_rules([
        {"rule_type": r.rule_type, "content": r.content, "priority": r.priority, "is_active": r.is_active}
        for r in rules
    ])

    system_prompt = build_dynamic_prompt(
        role=agent.role or "",
        target=agent.goal or "",
        rules_text=rules_text,
        system_prompt=agent.system_prompt or "",
    )

    if not system_prompt.strip():
        raise HTTPException(400, "Agent 需要先配置 system prompt 或 role")

    # Validate API key
    if not settings.aihubmix_api_key:
        raise HTTPException(500, "AIHubMix API key not configured")

    return StreamingResponse(
        run_conversation_test(
            agent_system_prompt=system_prompt,
            agent_opening_line=agent.opening_line,
            scenario=request.scenario,
            persona=request.persona,
            max_turns=request.max_turns,
            api_key=settings.aihubmix_api_key,
            base_url=settings.aihubmix_base_url,
            model=request.model,
            evaluate=request.evaluate,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
