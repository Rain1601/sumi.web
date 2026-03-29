"""Unified provider interfaces for ASR, TTS, and NLP.

All providers implement these abstract interfaces, ensuring hot-swappability.
ASR providers emit standardized events (START, CHANGE, END) regardless of vendor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


# ─── Audio Frame ─────────────────────────────────────────────────────────────

@dataclass
class AudioFrame:
    """A chunk of audio data."""
    data: bytes
    sample_rate: int = 16000
    num_channels: int = 1
    samples_per_channel: int = 0


# ─── ASR (Speech-to-Text) ───────────────────────────────────────────────────

class ASREventType(str, Enum):
    """Unified ASR events across all providers."""
    START = "asr_start"       # Speech detected, recognition starting
    CHANGE = "asr_change"     # Interim/partial result updated
    END = "asr_end"           # Final result, utterance complete


@dataclass
class ASREvent:
    """A single ASR event with type and data."""
    type: ASREventType
    text: str = ""
    confidence: float = 0.0
    language: str = ""
    is_final: bool = False
    alternatives: list[str] = field(default_factory=list)


@dataclass
class ASRConfig:
    """Configuration for an ASR streaming session."""
    language: str = "auto"          # "zh", "en", "auto"
    sample_rate: int = 16000
    encoding: str = "pcm"           # "pcm", "opus"
    interim_results: bool = True
    punctuation: bool = True
    model: str = ""                 # Provider-specific model name
    extra: dict[str, Any] = field(default_factory=dict)


class ASRStream(ABC):
    """Streaming ASR session. Push audio frames, receive events."""

    @abstractmethod
    async def push_frame(self, frame: AudioFrame) -> None:
        """Push an audio frame into the recognition stream."""
        ...

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[ASREvent]:
        """Iterate over ASR events as they arrive."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the stream and release resources."""
        ...


class ASRProvider(ABC):
    """Abstract ASR provider. All implementations emit unified ASREvent."""

    name: str  # e.g., "deepgram", "google_cloud", "alibaba"

    @abstractmethod
    async def create_stream(self, config: ASRConfig) -> ASRStream:
        """Create a new streaming recognition session."""
        ...


# ─── TTS (Text-to-Speech) ───────────────────────────────────────────────────

@dataclass
class TTSConfig:
    """Configuration for TTS synthesis."""
    voice: str = ""                 # Voice ID, provider-specific
    language: str = "zh"
    sample_rate: int = 24000
    speed: float = 1.0
    pitch: float = 1.0
    model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class TTSProvider(ABC):
    """Abstract TTS provider. Stream text in, stream audio out."""

    name: str

    @abstractmethod
    async def synthesize_stream(
        self,
        text_stream: AsyncIterator[str],
        config: TTSConfig,
    ) -> AsyncIterator[AudioFrame]:
        """Stream text in, stream audio frames out.

        Supports sentence-level streaming: as text chunks arrive from the LLM,
        the TTS provider synthesizes and yields audio incrementally.
        """
        ...

    async def synthesize(self, text: str, config: TTSConfig) -> AsyncIterator[AudioFrame]:
        """Convenience: synthesize a complete text string."""

        async def _single():
            yield text

        async for frame in self.synthesize_stream(_single(), config):
            yield frame


# ─── NLP (Large Language Model) ──────────────────────────────────────────────

@dataclass
class NLPMessage:
    """A chat message."""
    role: str           # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ToolDefinition:
    """A tool that the LLM can call."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class NLPChunkType(str, Enum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_CALL_DONE = "tool_call_done"
    DONE = "done"


@dataclass
class NLPChunk:
    """A streaming chunk from the LLM."""
    type: NLPChunkType
    text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    tool_args: str = ""         # Accumulated JSON string for tool arguments


@dataclass
class NLPConfig:
    """Configuration for an NLP chat completion."""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


class NLPProvider(ABC):
    """Abstract NLP provider. Streaming chat with tool support."""

    name: str

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[NLPMessage],
        tools: list[ToolDefinition] | None,
        config: NLPConfig,
    ) -> AsyncIterator[NLPChunk]:
        """Streaming chat completion with optional tool calling."""
        ...
