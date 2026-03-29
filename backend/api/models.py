"""Provider Models CRUD API.

All models are accessed through AIHubMix (OpenAI-compatible gateway).
One API key, one base URL — just pick the model name.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.config import settings
from backend.db.models import ProviderModel, gen_uuid

router = APIRouter()

# Available models via AIHubMix gateway
PROVIDER_OPTIONS = {
    "asr": [
        {
            "name": "openai",
            "label": "OpenAI Whisper (via AIHubMix)",
            "models": ["whisper-1"],
            "config_schema": {"language": "string"},
        },
    ],
    "tts": [
        {
            "name": "openai",
            "label": "OpenAI TTS (via AIHubMix)",
            "models": ["tts-1", "tts-1-hd", "tts-4o-mini"],
            "config_schema": {
                "voice": "string",
                "speed": "number",
            },
            "voices": ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"],
        },
    ],
    "nlp": [
        {
            "name": "anthropic",
            "label": "Anthropic Claude (via AIHubMix)",
            "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
            "config_schema": {"temperature": "number", "max_tokens": "number"},
        },
        {
            "name": "openai",
            "label": "OpenAI GPT (via AIHubMix)",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
            "config_schema": {"temperature": "number", "max_tokens": "number"},
        },
        {
            "name": "google",
            "label": "Google Gemini (via AIHubMix)",
            "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
            "config_schema": {"temperature": "number", "max_tokens": "number"},
        },
        {
            "name": "deepseek",
            "label": "DeepSeek (via AIHubMix)",
            "models": ["deepseek-chat", "deepseek-reasoner"],
            "config_schema": {"temperature": "number", "max_tokens": "number"},
        },
        {
            "name": "qwen",
            "label": "Alibaba Qwen (via AIHubMix)",
            "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
            "config_schema": {"temperature": "number", "max_tokens": "number"},
        },
    ],
}


class ProviderModelCreate(BaseModel):
    name: str
    provider_type: str        # "asr" | "tts" | "nlp"
    provider_name: str        # "openai" | "anthropic" | "google" | "deepseek" | "qwen"
    model_name: str = ""
    config: dict = {}


class ProviderModelUpdate(BaseModel):
    name: str | None = None
    model_name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ProviderModelResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    provider_name: str
    model_name: str
    config: dict
    is_active: bool
    created_at: str
    updated_at: str


class GatewayStatusResponse(BaseModel):
    base_url: str
    has_api_key: bool


def _to_response(m: ProviderModel) -> ProviderModelResponse:
    return ProviderModelResponse(
        id=m.id,
        name=m.name,
        provider_type=m.provider_type,
        provider_name=m.provider_name,
        model_name=m.model_name,
        config=m.config or {},
        is_active=m.is_active,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat(),
    )


@router.get("/gateway", response_model=GatewayStatusResponse)
async def get_gateway_status():
    """Check AIHubMix gateway configuration status."""
    return GatewayStatusResponse(
        base_url=settings.aihubmix_base_url,
        has_api_key=bool(settings.aihubmix_api_key),
    )


@router.get("/options")
async def get_provider_options():
    """Get available provider types and their models via AIHubMix."""
    return PROVIDER_OPTIONS


@router.get("/", response_model=list[ProviderModelResponse])
async def list_models(db: DbSession, provider_type: str | None = None):
    """List all configured models."""
    query = select(ProviderModel).order_by(ProviderModel.provider_type, ProviderModel.name)
    if provider_type:
        query = query.where(ProviderModel.provider_type == provider_type)
    result = await db.execute(query)
    return [_to_response(m) for m in result.scalars().all()]


@router.post("/", response_model=ProviderModelResponse)
async def create_model(req: ProviderModelCreate, db: DbSession):
    """Create a new model configuration (all go through AIHubMix gateway)."""
    if req.provider_type not in ("asr", "tts", "nlp"):
        raise HTTPException(400, "provider_type must be 'asr', 'tts', or 'nlp'")

    model = ProviderModel(
        id=gen_uuid(),
        name=req.name,
        provider_type=req.provider_type,
        provider_name=req.provider_name,
        api_key="",  # No per-model key — uses global AIHubMix key
        model_name=req.model_name,
        config=req.config,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _to_response(model)


@router.get("/{model_id}", response_model=ProviderModelResponse)
async def get_model(model_id: str, db: DbSession):
    result = await db.execute(select(ProviderModel).where(ProviderModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")
    return _to_response(model)


@router.patch("/{model_id}", response_model=ProviderModelResponse)
async def update_model(model_id: str, req: ProviderModelUpdate, db: DbSession):
    result = await db.execute(select(ProviderModel).where(ProviderModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")

    if req.name is not None:
        model.name = req.name
    if req.model_name is not None:
        model.model_name = req.model_name
    if req.config is not None:
        model.config = req.config
    if req.is_active is not None:
        model.is_active = req.is_active

    await db.commit()
    await db.refresh(model)
    return _to_response(model)


@router.delete("/{model_id}")
async def delete_model(model_id: str, db: DbSession):
    result = await db.execute(select(ProviderModel).where(ProviderModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, "Model not found")
    await db.delete(model)
    await db.commit()
    return {"ok": True}
