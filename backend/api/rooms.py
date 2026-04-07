import logging

from fastapi import APIRouter, HTTPException
from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from pydantic import BaseModel

from backend.api.deps import CurrentUserId
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

AGENT_NAME = "kodama-agent"


class CreateRoomRequest(BaseModel):
    agent_id: str


class CreateRoomResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str


class WorkerStatusResponse(BaseModel):
    available: bool
    agent_count: int
    message: str


def _lk_api() -> LiveKitAPI:
    lk_api_url = settings.livekit_url.replace("ws://", "http://").replace("wss://", "https://")
    return LiveKitAPI(url=lk_api_url, api_key=settings.livekit_api_key, api_secret=settings.livekit_api_secret)


@router.get("/worker-status", response_model=WorkerStatusResponse)
async def worker_status():
    """Check if LiveKit server is reachable and worker can be dispatched."""
    from livekit.api import ListRoomsRequest
    api = _lk_api()
    try:
        # list_rooms is a lightweight call to verify LiveKit server connectivity
        rooms = await api.room.list_rooms(ListRoomsRequest())
        room_count = len(rooms.rooms) if rooms.rooms else 0
        return WorkerStatusResponse(
            available=True,
            agent_count=room_count,
            message=f"LiveKit 正常 · {room_count} 个房间",
        )
    except Exception as e:
        logger.warning(f"[ROOM] worker status check failed: {e}")
        return WorkerStatusResponse(
            available=False,
            agent_count=0,
            message=f"LiveKit 不可用: {e}",
        )
    finally:
        await api.aclose()


@router.post("/worker-restart")
async def worker_restart():
    """Force restart the worker by killing all worker processes.
    In dev: pkill + spawn new process.
    In production (Cloud Run): worker runs as separate service, can only kill local."""
    import subprocess
    import sys
    try:
        # Kill existing worker processes
        result = subprocess.run(
            ["pkill", "-9", "-f", "backend.pipeline.worker"],
            capture_output=True, text=True, timeout=5,
        )
        killed = result.returncode == 0

        if settings.is_dev:
            # Dev mode: start a new worker in background using current Python
            subprocess.Popen(
                [sys.executable, "-m", "backend.pipeline.worker", "start"],
                stdout=open("/tmp/kodama_worker.log", "w"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            return {
                "ok": True,
                "killed": killed,
                "message": "Worker 已重启" if killed else "未找到旧进程，已启动新 Worker",
            }
        else:
            # Production: worker is a separate Cloud Run service
            # Can only signal that a restart is needed
            return {
                "ok": killed,
                "killed": killed,
                "message": "Worker 进程已终止" if killed else "生产环境 Worker 为独立服务，请通过 Cloud Run 控制台重启",
            }
    except Exception as e:
        logger.error(f"[ROOM] worker restart failed: {e}")
        raise HTTPException(status_code=500, detail=f"重启失败: {e}")


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(req: CreateRoomRequest, user_id: CurrentUserId):
    """Create room + dispatch agent. Simple and reliable."""
    room_name = f"kodama_{user_id}_{req.agent_id}"

    lk_ws_url = settings.livekit_url
    logger.info(f"[ROOM] creating room={room_name} livekit_url={lk_ws_url}")

    # Dispatch agent
    api = _lk_api()
    dispatch_ok = False
    try:
        dispatch = await api.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(room=room_name, agent_name=AGENT_NAME)
        )
        dispatch_ok = True
        logger.info(f"[ROOM] dispatch OK: {dispatch.id} room={room_name}")
    except Exception as e:
        logger.error(f"[ROOM] dispatch ERROR: {e}")
    finally:
        await api.aclose()

    if not dispatch_ok:
        raise HTTPException(status_code=503, detail="Worker 不可用，请检查 worker 是否已启动")

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
