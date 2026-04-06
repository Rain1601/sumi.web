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
    """Create room + dispatch agent. Simple and reliable."""
    room_name = f"sumi_{user_id}_{req.agent_id}"

    lk_ws_url = settings.livekit_url
    logger.info(f"[ROOM] creating room={room_name} livekit_url={lk_ws_url}")

    # Dispatch agent
    lk_api_url = lk_ws_url.replace("ws://", "http://").replace("wss://", "https://")
    api = LiveKitAPI(url=lk_api_url, api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret)
    try:
        dispatch = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(room=room_name, agent_name=AGENT_NAME)
        )
        logger.info(f"[ROOM] dispatch OK: {dispatch.id} room={room_name}")
    except Exception as e:
        logger.error(f"[ROOM] dispatch ERROR (lk_api_url={lk_api_url}): {e}")
    finally:
        await api.aclose()

    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(user_id)
        .with_name(user_id)
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .with_metadata(req.agent_id)
    )

    return CreateRoomResponse(
        room_name=room_name,
        token=token.to_jwt(),
        livekit_url=lk_ws_url,
    )
