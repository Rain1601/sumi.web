"""Agent Audio Init API — upload audio file, transcribe, extract SOP via LLM."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from backend.api.deps import DbSession
from backend.config import settings
from backend.db.models import Agent
from backend.services.audio_init import init_from_audio_stream

router = APIRouter()

ALLOWED_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/x-m4a", "audio/mp4", "audio/m4a", "audio/ogg",
    "audio/webm",
}
MAX_SIZE_MB = 100
AUDIO_INIT_DIR = Path("data/audio/init")


@router.post("/{agent_id}/init-from-audio")
async def init_agent_from_audio(
    agent_id: str,
    file: UploadFile,
    db: DbSession,
):
    """Upload an audio file and return an SSE stream with transcription + SOP extraction."""

    # Validate agent exists
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    # Validate file type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        # Also check by extension
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
        if ext not in {"mp3", "wav", "m4a", "ogg", "webm", "mp4"}:
            raise HTTPException(400, f"Unsupported file type: {content_type}. Use mp3/wav/m4a.")

    # Validate API keys are configured
    if not settings.dashscope_api_key:
        raise HTTPException(500, "DashScope API key not configured")
    if not settings.aihubmix_api_key:
        raise HTTPException(500, "AIHubMix API key not configured")

    # Save file
    AUDIO_INIT_DIR.mkdir(parents=True, exist_ok=True)
    ext = (file.filename or "audio.mp3").rsplit(".", 1)[-1].lower()
    saved_name = f"{uuid.uuid4()}.{ext}"
    saved_path = AUDIO_INIT_DIR / saved_name

    total_bytes = 0
    with open(saved_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_bytes += len(chunk)
            if total_bytes > MAX_SIZE_MB * 1024 * 1024:
                saved_path.unlink(missing_ok=True)
                raise HTTPException(400, f"File too large (max {MAX_SIZE_MB}MB)")
            f.write(chunk)

    # Build file URL for DashScope (if accessible externally)
    file_url = f"{settings.app_base_url}/api/audio/init/{saved_name}" if settings.app_base_url else None

    # Return SSE stream
    return StreamingResponse(
        init_from_audio_stream(
            file_path=saved_path,
            dashscope_api_key=settings.dashscope_api_key,
            aihubmix_api_key=settings.aihubmix_api_key,
            aihubmix_base_url=settings.aihubmix_base_url,
            file_url=file_url,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
