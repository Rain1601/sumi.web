"""Pipeline event types used for tracing and debugging."""

from enum import Enum


class PipelineEventType(str, Enum):
    # VAD events
    VAD_SPEECH_START = "vad.speech_start"
    VAD_SPEECH_END = "vad.speech_end"

    # ASR events (unified across providers)
    ASR_START = "asr.start"
    ASR_CHANGE = "asr.change"
    ASR_END = "asr.end"

    # NLP events
    NLP_START = "nlp.start"
    NLP_CHUNK = "nlp.chunk"
    NLP_TOOL_CALL = "nlp.tool_call"
    NLP_TOOL_RESULT = "nlp.tool_result"
    NLP_END = "nlp.end"

    # TTS events
    TTS_START = "tts.start"
    TTS_CHUNK = "tts.chunk"
    TTS_END = "tts.end"

    # Pipeline lifecycle
    INTERRUPTION = "pipeline.interruption"
    AGENT_SWITCH = "agent.switch"
    SESSION_START = "session.start"
    SESSION_END = "session.end"

    # Memory events
    MEMORY_QUERY = "memory.query"
    MEMORY_UPDATE = "memory.update"

    # Errors
    ERROR = "error"
