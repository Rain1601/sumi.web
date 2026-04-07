"""Agent Voice Test API — run voice adversarial dialogue test via SSE."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.deps import Auth, DbSession
from backend.config import settings
from backend.db.models import Agent, AgentRule
from backend.pipeline.prompt_builder import build_dynamic_prompt, format_rules
from backend.services.voice_test import run_voice_test

router = APIRouter()


class VoiceTestRequest(BaseModel):
    scenario: str = Field(..., description="测试场景描述")
    persona: str = Field("", description="模拟用户人设（留空自动生成）")
    max_turns: int = Field(10, ge=2, le=30, description="最大对话回合数")
    evaluate: bool = Field(True, description="是否在对话结束后评估")
    model: str = Field("claude-sonnet-4-20250514", description="LLM 模型")
    audio_enabled: bool = Field(False, description="是否启用语音（需要 LiveKit）")
    agent_tts_model_id: str | None = Field(None, description="Agent TTS 模型 ID")
    tester_tts_model_id: str | None = Field(None, description="Tester TTS 模型 ID")


@router.post("/{agent_id}/voice-test")
async def run_agent_voice_test(
    agent_id: str,
    request: VoiceTestRequest,
    auth: Auth,
    db: DbSession,
):
    """Run a voice adversarial test for an agent, streamed via SSE."""

    # Load agent
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

    # Build runtime prompt
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

    if not settings.aihubmix_api_key:
        raise HTTPException(500, "AIHubMix API key not configured")

    # Phase 2: Resolve TTS model info
    agent_tts_info = None
    tester_tts_info = None
    if request.audio_enabled:
        from backend.db.models import ProviderModel
        if request.agent_tts_model_id:
            r = await db.execute(select(ProviderModel).where(ProviderModel.id == request.agent_tts_model_id))
            m = r.scalar_one_or_none()
            if m:
                agent_tts_info = {"provider_name": m.provider_name, "model_name": m.model_name, "config": m.config}
        elif agent.tts_model_id:
            r = await db.execute(select(ProviderModel).where(ProviderModel.id == agent.tts_model_id))
            m = r.scalar_one_or_none()
            if m:
                agent_tts_info = {"provider_name": m.provider_name, "model_name": m.model_name, "config": m.config}

        if request.tester_tts_model_id:
            r = await db.execute(select(ProviderModel).where(ProviderModel.id == request.tester_tts_model_id))
            m = r.scalar_one_or_none()
            if m:
                tester_tts_info = {"provider_name": m.provider_name, "model_name": m.model_name, "config": m.config}

    return StreamingResponse(
        run_voice_test(
            agent_system_prompt=system_prompt,
            agent_opening_line=agent.opening_line,
            scenario=request.scenario,
            persona=request.persona,
            max_turns=request.max_turns,
            api_key=settings.aihubmix_api_key,
            base_url=settings.aihubmix_base_url,
            model=request.model,
            evaluate=request.evaluate,
            audio_enabled=request.audio_enabled,
            agent_tts_info=agent_tts_info,
            tester_tts_info=tester_tts_info,
            livekit_url=settings.livekit_url if request.audio_enabled else None,
            livekit_api_key=settings.livekit_api_key if request.audio_enabled else None,
            livekit_api_secret=settings.livekit_api_secret if request.audio_enabled else None,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
