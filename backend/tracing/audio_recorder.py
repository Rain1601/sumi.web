"""Audio recorder for capturing per-turn and full conversation audio.

Captures PCM frames from user (WebRTC track) and agent (TTS output),
segments by turn, and writes WAV files to disk.
"""

import asyncio
import io
import logging
import struct
import time
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from livekit import rtc

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio"


def _write_wav(path: Path, pcm_data: bytes, sample_rate: int, num_channels: int = 1):
    """Write raw PCM int16 data to a WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    logger.debug(f"[AUDIO] Wrote {path} ({len(pcm_data)} bytes, {sample_rate}Hz)")


class TurnAudioBuffer:
    """Accumulates PCM frames for a single turn (user or agent)."""

    def __init__(self, role: str, turn_index: int, sample_rate: int = 16000):
        self.role = role
        self.turn_index = turn_index
        self.sample_rate = sample_rate
        self._chunks: list[bytes] = []

    def push(self, pcm_data: bytes):
        self._chunks.append(pcm_data)

    @property
    def pcm_bytes(self) -> bytes:
        return b"".join(self._chunks)

    @property
    def duration_s(self) -> float:
        total_bytes = sum(len(c) for c in self._chunks)
        return total_bytes / (self.sample_rate * 2)  # 16-bit = 2 bytes/sample

    @property
    def is_empty(self) -> bool:
        return len(self._chunks) == 0


class AudioRecorder:
    """Records per-turn audio and full conversation audio for a session.

    Usage:
        recorder = AudioRecorder(conversation_id, sample_rate=16000)
        # Start user turn
        recorder.start_user_turn(turn_index=0)
        recorder.push_user_audio(pcm_bytes)
        path = recorder.end_user_turn()  # returns wav path

        # Start agent turn
        recorder.start_agent_turn(turn_index=0)
        recorder.push_agent_audio(frame)
        path = recorder.end_agent_turn()  # returns wav path

        # Finalize — writes full conversation WAV
        recorder.finalize()
    """

    def __init__(self, conversation_id: str, sample_rate: int = 16000):
        self._conversation_id = conversation_id
        self._sample_rate = sample_rate
        self._dir = AUDIO_DIR / conversation_id
        self._dir.mkdir(parents=True, exist_ok=True)

        self._user_buf: TurnAudioBuffer | None = None
        self._agent_buf: TurnAudioBuffer | None = None

        # Full conversation: interleaved PCM (for full audio export)
        self._full_chunks: list[bytes] = []
        self._turn_files: list[dict] = []  # [{role, turn_index, path, duration_s}]

    @property
    def base_dir(self) -> Path:
        return self._dir

    # --- User audio (from WebRTC track) ---

    def start_user_turn(self, turn_index: int):
        self._user_buf = TurnAudioBuffer("user", turn_index, self._sample_rate)

    def push_user_audio(self, frame: rtc.AudioFrame):
        """Push a user audio frame (from AudioStream)."""
        if self._user_buf is None:
            return
        pcm = bytes(frame.data)
        self._user_buf.push(pcm)
        self._full_chunks.append(pcm)

    def end_user_turn(self) -> str | None:
        """End user turn, write WAV, return relative path."""
        if self._user_buf is None or self._user_buf.is_empty:
            self._user_buf = None
            return None

        filename = f"user_{self._user_buf.turn_index:03d}.wav"
        path = self._dir / filename
        _write_wav(path, self._user_buf.pcm_bytes, self._user_buf.sample_rate)

        rel_path = f"audio/{self._conversation_id}/{filename}"
        self._turn_files.append({
            "role": "user",
            "turn_index": self._user_buf.turn_index,
            "path": rel_path,
            "duration_s": self._user_buf.duration_s,
        })
        logger.info(
            f"[AUDIO][USER ] turn={self._user_buf.turn_index} "
            f"dur={self._user_buf.duration_s:.1f}s file={filename}"
        )
        self._user_buf = None
        return rel_path

    # --- Agent audio (from TTS output) ---

    def start_agent_turn(self, turn_index: int, sample_rate: int | None = None):
        sr = sample_rate or self._sample_rate
        self._agent_buf = TurnAudioBuffer("assistant", turn_index, sr)

    def push_agent_audio(self, frame: rtc.AudioFrame):
        """Push an agent TTS audio frame."""
        if self._agent_buf is None:
            return
        # Use frame's actual sample rate
        if frame.sample_rate and frame.sample_rate != self._agent_buf.sample_rate:
            self._agent_buf.sample_rate = frame.sample_rate
        pcm = bytes(frame.data)
        self._agent_buf.push(pcm)
        self._full_chunks.append(pcm)

    def end_agent_turn(self) -> str | None:
        """End agent turn, write WAV, return relative path."""
        if self._agent_buf is None or self._agent_buf.is_empty:
            self._agent_buf = None
            return None

        filename = f"agent_{self._agent_buf.turn_index:03d}.wav"
        path = self._dir / filename
        _write_wav(path, self._agent_buf.pcm_bytes, self._agent_buf.sample_rate)

        rel_path = f"audio/{self._conversation_id}/{filename}"
        self._turn_files.append({
            "role": "assistant",
            "turn_index": self._agent_buf.turn_index,
            "path": rel_path,
            "duration_s": self._agent_buf.duration_s,
        })
        logger.info(
            f"[AUDIO][AGENT] turn={self._agent_buf.turn_index} "
            f"dur={self._agent_buf.duration_s:.1f}s file={filename}"
        )
        self._agent_buf = None
        return rel_path

    # --- Full conversation ---

    def finalize(self) -> str | None:
        """Write full conversation WAV. Returns relative path."""
        if not self._full_chunks:
            return None

        filename = "full.wav"
        path = self._dir / filename
        full_pcm = b"".join(self._full_chunks)
        _write_wav(path, full_pcm, self._sample_rate)

        rel_path = f"audio/{self._conversation_id}/{filename}"
        duration_s = len(full_pcm) / (self._sample_rate * 2)
        logger.info(
            f"[AUDIO][FULL ] conversation={self._conversation_id} "
            f"dur={duration_s:.1f}s turns={len(self._turn_files)} file={filename}"
        )
        return rel_path

    @property
    def turn_files(self) -> list[dict]:
        return self._turn_files
