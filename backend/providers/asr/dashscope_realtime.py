"""DashScope Realtime API STT adapter for LiveKit Agents.

Uses the OpenAI Realtime compatible API (wss://dashscope.aliyuncs.com/api-ws/v1/realtime).
Supports: qwen3-asr-flash-realtime, fun-asr-realtime, paraformer-realtime-v2
Built-in server-side VAD — no need for Silero.
"""

import asyncio
import base64
import json
import logging
import time

import websockets
from livekit import rtc
from livekit.agents import stt, NOT_GIVEN, APIConnectOptions

from backend.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONN = APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=10.0)


class DashScopeRealtimeSTT(stt.STT):
    def __init__(
        self,
        *,
        model: str = "qwen3-asr-flash-realtime",
        language: str = "zh",
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        silence_duration_ms: int = 400,
        api_key: str = "",
        base_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
    ):
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=True,
                interim_results=True,
            )
        )
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._vad_threshold = vad_threshold
        self._silence_duration_ms = silence_duration_ms
        self._api_key = api_key or settings.dashscope_api_key
        self._base_url = base_url

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None):
        raise NotImplementedError("Use stream() — this is a streaming-only STT")

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_CONN):
        return DashScopeRealtimeStream(
            stt=self,
            conn_options=conn_options,
            model=self._model,
            language=self._language,
            sample_rate=self._sample_rate,
            vad_threshold=self._vad_threshold,
            silence_duration_ms=self._silence_duration_ms,
            api_key=self._api_key,
            base_url=self._base_url,
        )


class DashScopeRealtimeStream(stt.RecognizeStream):
    def __init__(self, *, stt, conn_options, model, language, sample_rate,
                 vad_threshold, silence_duration_ms, api_key, base_url, **kwargs):
        super().__init__(stt=stt, conn_options=conn_options)
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._vad_threshold = vad_threshold
        self._silence_duration_ms = silence_duration_ms
        self._api_key = api_key
        self._base_url = base_url

    async def _run(self):
        """Connect to DashScope Realtime API, stream audio, receive transcripts."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._run_session()
                return
            except Exception as e:
                logger.warning(f"[ASR REALTIME] Session failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                else:
                    logger.error(f"[ASR REALTIME] Max retries reached")

    async def _run_session(self):
        url = f"{self._base_url}?model={self._model}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        async with websockets.connect(
            url,
            additional_headers=headers,
            ping_interval=15,
            ping_timeout=10,
            max_size=2**20,
        ) as ws:
            logger.info(f"[ASR REALTIME] Connected, model={self._model}")

            # Wait for session.created
            resp = json.loads(await ws.recv())
            if resp.get("type") != "session.created":
                raise Exception(f"Expected session.created, got {resp.get('type')}")

            # Send session.update with VAD config
            await ws.send(json.dumps({
                "event_id": "init",
                "type": "session.update",
                "session": {
                    "modalities": ["text"],
                    "input_audio_format": "pcm",
                    "sample_rate": self._sample_rate,
                    "input_audio_transcription": {
                        "language": self._language,
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": self._vad_threshold,
                        "silence_duration_ms": self._silence_duration_ms,
                    },
                },
            }))

            logger.info(f"[ASR REALTIME] Session configured: lang={self._language} vad_threshold={self._vad_threshold}")

            # Run send + receive concurrently
            send_task = asyncio.create_task(self._send_audio(ws))
            recv_task = asyncio.create_task(self._recv_results(ws))

            await asyncio.gather(send_task, recv_task)

    async def _send_audio(self, ws):
        """Read audio frames from LiveKit and send as base64 to Realtime API."""
        try:
            async for frame in self._input_ch:
                if isinstance(frame, rtc.AudioFrame):
                    pcm_bytes = frame.data.tobytes()
                    encoded = base64.b64encode(pcm_bytes).decode('utf-8')
                    await ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": encoded,
                    }))
        except Exception:
            pass

        # Input ended — send finish
        try:
            await ws.send(json.dumps({"type": "session.finish"}))
        except Exception:
            pass

    async def _recv_results(self, ws):
        """Receive events from Realtime API and emit SpeechEvents."""
        speech_started = False

        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue

                data = json.loads(msg)
                evt_type = data.get("type", "")

                if evt_type == "input_audio_buffer.speech_started":
                    if not speech_started:
                        speech_started = True
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                        )
                        logger.info("[ASR REALTIME] Speech started")

                elif evt_type == "conversation.item.input_audio_transcription.text":
                    # Interim result
                    text = data.get("text", "")
                    if text:
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                alternatives=[
                                    stt.SpeechData(language=self._language, text=text, confidence=0.8)
                                ],
                            )
                        )
                        logger.info(f"[ASR REALTIME] Interim: \"{text}\"")

                elif evt_type == "conversation.item.input_audio_transcription.completed":
                    # Final result
                    text = data.get("transcript", "")
                    if text:
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                                alternatives=[
                                    stt.SpeechData(language=self._language, text=text, confidence=1.0)
                                ],
                            )
                        )
                        logger.info(f"[ASR REALTIME] Final: \"{text}\"")

                    self._event_ch.send_nowait(
                        stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH)
                    )
                    speech_started = False

                elif evt_type == "input_audio_buffer.speech_stopped":
                    logger.debug("[ASR REALTIME] Speech stopped (VAD)")

                elif evt_type == "session.finished":
                    logger.info("[ASR REALTIME] Session finished")
                    break

                elif evt_type == "error":
                    err = data.get("error", {}).get("message", str(data))
                    logger.error(f"[ASR REALTIME] Error: {err}")
                    break

                elif evt_type == "session.updated":
                    logger.debug("[ASR REALTIME] Session updated")

        except websockets.exceptions.ConnectionClosed:
            pass
