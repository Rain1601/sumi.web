"""Voiceprint-filtered STT wrapper.

Wraps any LiveKit STT to add speaker verification.
First utterance auto-enrolls. Non-primary speakers are silently filtered.
Sends voiceprint events via LiveKit data channel to frontend.
"""

import json
import logging
import numpy as np
from livekit import rtc
from livekit.agents import stt, NOT_GIVEN, APIConnectOptions

from backend.pipeline.voiceprint import SpeakerVerifier

logger = logging.getLogger(__name__)

DEFAULT_CONN = APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=10.0)


class VoiceprintSTT(stt.STT):
    """Wraps an inner STT with speaker verification."""

    def __init__(self, inner_stt: stt.STT, model: str = "resemblyzer", threshold: float = 0.65):
        super().__init__(capabilities=inner_stt._capabilities)
        self._inner = inner_stt
        self._verifier = SpeakerVerifier(model=model, threshold=threshold)
        self._room: rtc.Room | None = None
        logger.info(f"[VOICEPRINT] Initialized with model={model} threshold={threshold}")

    def set_room(self, room: rtc.Room):
        """Set the LiveKit room for sending data channel events."""
        self._room = room

    async def _send_event(self, event_type: str, data: dict):
        """Send voiceprint event to frontend via data channel."""
        if self._room and self._room.local_participant:
            try:
                payload = json.dumps({"type": event_type, **data}).encode()
                await self._room.local_participant.publish_data(payload, topic="voiceprint")
            except Exception as e:
                logger.debug(f"[VOICEPRINT] Failed to send event: {e}")

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None):
        return await self._inner.recognize(buffer, language=language, conn_options=conn_options)

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_CONN):
        inner_stream = self._inner.stream(language=language, conn_options=conn_options)
        return VoiceprintRecognizeStream(
            inner_stream=inner_stream,
            verifier=self._verifier,
            room=self._room,
            stt=self,
            conn_options=conn_options,
        )


class VoiceprintRecognizeStream(stt.RecognizeStream):
    """Collects audio frames, verifies speaker on speech end, filters non-primary."""

    def __init__(self, *, inner_stream, verifier, room, stt, conn_options):
        super().__init__(stt=stt, conn_options=conn_options)
        self._inner = inner_stream
        self._verifier = verifier
        self._room = room
        self._audio_buffer: list[np.ndarray] = []

    async def _send_event(self, event_type: str, data: dict):
        if self._room and self._room.local_participant:
            try:
                payload = json.dumps({"type": event_type, **data}).encode()
                await self._room.local_participant.publish_data(payload, topic="voiceprint")
            except Exception:
                pass

    async def _run(self):
        import asyncio

        async def forward_input():
            async for frame in self._input_ch:
                if hasattr(frame, 'data'):
                    pcm = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0
                    self._audio_buffer.append(pcm)
                self._inner.push_frame(frame)
            self._inner.end_input()

        async def filter_output():
            async for event in self._inner:
                if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    text = event.alternatives[0].text[:60] if event.alternatives else ""

                    if self._audio_buffer:
                        audio = np.concatenate(self._audio_buffer)
                        is_primary, score = self._verifier.process_audio(audio, 16000)
                        self._audio_buffer.clear()

                        # Send event to frontend
                        await self._send_event("voiceprint_result", {
                            "is_primary": is_primary,
                            "score": round(score, 3),
                            "text": text,
                            "is_anchor": self._verifier._anchor_embedding is not None and score == 1.0,
                        })

                        if is_primary:
                            logger.info(f"[VOICEPRINT] PASS score={score:.3f} text=\"{text}\"")
                            self._event_ch.send_nowait(event)
                        else:
                            logger.info(f"[VOICEPRINT] REJECT score={score:.3f} text=\"{text}\"")
                            # Don't forward FINAL — agent stays in listening, won't respond
                    else:
                        self._event_ch.send_nowait(event)

                elif event.type == stt.SpeechEventType.END_OF_SPEECH:
                    self._audio_buffer.clear()
                    self._event_ch.send_nowait(event)
                else:
                    self._event_ch.send_nowait(event)

        await asyncio.gather(forward_input(), filter_output())
