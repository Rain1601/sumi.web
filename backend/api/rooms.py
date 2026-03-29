import logging

from fastapi import APIRouter
from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from pydantic import BaseModel

from backend.api.deps import CurrentUserId
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

AGENT_NAME = "sumi-agent"


class CreateRoomRequest(BaseModel):
    agent_id: str


class CreateRoomResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(req: CreateRoomRequest, user_id: CurrentUserId):
    """Create room + dispatch named agent."""
    room_name = f"sumi_{user_id}_{req.agent_id}"

    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(user_id)
        .with_name(user_id)
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .with_metadata(req.agent_id)
    )

    # Dispatch our named agent
    try:
        lk_url = settings.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
        api = LiveKitAPI(url=lk_url, api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret)
        dispatch = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(room=room_name, agent_name=AGENT_NAME)
        )
        logger.info(f"[ROOM] room={room_name} dispatch={dispatch.id}")
        await api.aclose()
    except Exception as e:
        logger.warning(f"[ROOM] Dispatch error: {e}")

    return CreateRoomResponse(
        room_name=room_name,
        token=token.to_jwt(),
        livekit_url=settings.livekit_url,
    )
