"""Voiceprint-filtered STT wrapper.

Wraps any LiveKit STT to add speaker verification.
First utterance auto-enrolls. Non-primary speakers are silently filtered.
"""

import logging
import numpy as np
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
        logger.info(f"[VOICEPRINT] Initialized with model={model} threshold={threshold}")

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None):
        return await self._inner.recognize(buffer, language=language, conn_options=conn_options)

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_CONN):
        inner_stream = self._inner.stream(language=language, conn_options=conn_options)
        return VoiceprintRecognizeStream(
            inner_stream=inner_stream,
            verifier=self._verifier,
            stt=self,
            conn_options=conn_options,
        )


class VoiceprintRecognizeStream(stt.RecognizeStream):
    """Collects audio frames, verifies speaker on speech end, filters non-primary."""

    def __init__(self, *, inner_stream, verifier, stt, conn_options):
        super().__init__(stt=stt, conn_options=conn_options)
        self._inner = inner_stream
        self._verifier = verifier
        self._audio_buffer: list[np.ndarray] = []

    async def _run(self):
        """Proxy audio to inner STT, but filter transcripts from non-primary speakers."""
        import asyncio

        # We need to:
        # 1. Forward all audio frames to inner STT (it needs them for recognition)
        # 2. Collect audio for voiceprint verification
        # 3. When we get a FINAL_TRANSCRIPT, verify the speaker
        # 4. Only emit the transcript if speaker matches

        async def forward_input():
            """Forward audio frames from our input to inner STT."""
            async for frame in self._input_ch:
                # Collect for voiceprint
                if hasattr(frame, 'data'):
                    pcm = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0
                    self._audio_buffer.append(pcm)
                # Forward to inner STT
                self._inner.push_frame(frame)

            # Input ended
            self._inner.end_input()

        async def filter_output():
            """Read events from inner STT, filter by voiceprint."""
            async for event in self._inner:
                if event.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    # Verify speaker using collected audio
                    if self._audio_buffer:
                        audio = np.concatenate(self._audio_buffer)
                        is_primary, score = self._verifier.process_audio(audio, 16000)
                        self._audio_buffer.clear()

                        if is_primary:
                            logger.info(f"[VOICEPRINT] PASS score={score:.3f} text=\"{event.alternatives[0].text[:50] if event.alternatives else ''}\"")
                            self._event_ch.send_nowait(event)
                        else:
                            logger.info(f"[VOICEPRINT] REJECT score={score:.3f} text=\"{event.alternatives[0].text[:50] if event.alternatives else ''}\"")
                            # Don't emit — this utterance is from a different speaker
                    else:
                        # No audio collected, pass through
                        self._event_ch.send_nowait(event)

                elif event.type == stt.SpeechEventType.END_OF_SPEECH:
                    # Clear audio buffer on speech end
                    self._audio_buffer.clear()
                    self._event_ch.send_nowait(event)

                else:
                    # INTERIM, START_OF_SPEECH etc — pass through
                    self._event_ch.send_nowait(event)

        await asyncio.gather(forward_input(), filter_output())
