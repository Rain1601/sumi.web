from pydantic import BaseModel
from typing import Any

class VadData(BaseModel):
    duration_ms: float

class AsrData(BaseModel):
    transcript: str = ""
    language: str = ""
    is_final: bool = False
    confidence: float = 0.0
    latency_ms: float | None = None     # vad_end → asr_final
    audio_ref: str | None = None

class NlpData(BaseModel):
    text: str = ""
    token_count: int = 0
    ttfb_ms: float | None = None        # time to first token
    ttf10t_ms: float | None = None      # time to 10th token
    total_ms: float | None = None
    model: str = ""

class TtsData(BaseModel):
    text: str = ""
    first_audio_ms: float | None = None
    total_ms: float | None = None
    subtitle_alignment: list[dict] | None = None

class ToolCallData(BaseModel):
    tool_name: str
    params: dict[str, Any] = {}
    result: Any = None
    duration_ms: float | None = None
    call_time: float | None = None

class InterruptionData(BaseModel):
    position_ms: float
    agent_text_spoken: str = ""
    agent_text_cut: str = ""
    is_interruption: bool = False
    probability: float = 0.0
    detection_delay_ms: float = 0.0

class VoiceprintData(BaseModel):
    score: float
    accepted: bool
    threshold: float = 0.65

class ErrorData(BaseModel):
    source: str
    message: str

class SessionData(BaseModel):
    room_name: str = ""
    user_id: str = ""
    agent_id: str = ""
    total_duration_ms: float | None = None

class UserTurnData(BaseModel):
    turn_index: int
    user_speech_start_time: float
    asr_start_time: float | None = None
    vad_duration_ms: float
    asr_final_time: float
    asr_result: str
    asr_latency_ms: float
    audio_ref: str | None = None

class AgentTurnData(BaseModel):
    turn_index: int
    nlp_request_time: float
    nlp_ttfb_ms: float | None = None
    nlp_ttf10t_ms: float | None = None
    nlp_complete_time: float | None = None
    nlp_result: str = ""
    tts_start_time: float | None = None
    tts_first_audio_time: float | None = None
    tts_end_time: float | None = None
    tool_calls: list[ToolCallData] = []
    audio_ref: str | None = None
