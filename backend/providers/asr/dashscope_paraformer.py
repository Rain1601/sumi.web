"""DashScope Paraformer realtime STT adapter for LiveKit Agents.

Streams audio to Alibaba's Paraformer via WebSocket, receives interim/final results.
Built-in VAD via max_sentence_silence — no need for Silero.
"""

import asyncio
import json
import logging
import uuid

import websockets
from livekit import rtc
from livekit.agents import stt, NOT_GIVEN, APIConnectOptions

from backend.config import settings

DEFAULT_CONN = APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=10.0)

logger = logging.getLogger(__name__)


class ParaformerSTT(stt.STT):
    def __init__(
        self,
        *,
        model: str = "paraformer-realtime-v2",
        language: str = "zh",
        sample_rate: int = 16000,
        max_sentence_silence: int = 600,
        api_key: str = "",
        ws_url: str = "",
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
        self._max_sentence_silence = max_sentence_silence
        self._api_key = api_key or settings.dashscope_api_key
        self._ws_url = ws_url or settings.dashscope_ws_url

    async def _recognize_impl(self, buffer, *, language=None, conn_options=None):
        raise NotImplementedError("Use stream() for Paraformer — it's streaming-only")

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_CONN):
        return ParaformerRecognizeStream(
            stt=self,
            conn_options=conn_options if conn_options is not NOT_GIVEN else DEFAULT_CONN,
            model=self._model,
            language=self._language,
            sample_rate=self._sample_rate,
            max_sentence_silence=self._max_sentence_silence,
            api_key=self._api_key,
            ws_url=self._ws_url,
        )


class ParaformerRecognizeStream(stt.RecognizeStream):
    def __init__(self, *, stt, conn_options=DEFAULT_CONN, model, language, sample_rate, max_sentence_silence, api_key, ws_url, **kwargs):
        super().__init__(stt=stt, conn_options=conn_options)
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        self._max_sentence_silence = max_sentence_silence
        self._api_key = api_key
        self._ws_url = ws_url

    async def _run(self):
        """Main loop: connect to DashScope WebSocket, send audio, receive transcripts."""
        task_id = uuid.uuid4().hex
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            async with websockets.connect(
                self._ws_url,
                subprotocols=["chat"],
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                max_size=2**20,
            ) as ws:
                logger.info(f"[ASR DASHSCOPE] Connected to {self._ws_url}, model={self._model}")

                # Send run-task
                run_task = {
                    "header": {
                        "action": "run-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {
                        "task_group": "audio",
                        "task": "asr",
                        "function": "recognition",
                        "model": self._model,
                        "parameters": {
                            "format": "pcm",
                            "sample_rate": self._sample_rate,
                            "max_sentence_silence": self._max_sentence_silence,
                            "disfluency_removal_enabled": False,
                        },
                        "input": {},
                    },
                }
                await ws.send(json.dumps(run_task))

                # Wait for task-started
                resp = json.loads(await ws.recv())
                event_name = resp.get("header", {}).get("event", "")
                if event_name == "task-failed":
                    err = resp.get("header", {}).get("error_message", "unknown")
                    raise Exception(f"Paraformer task failed: {err}")
                if event_name != "task-started":
                    raise Exception(f"Unexpected event: {event_name}")

                logger.info(f"[ASR DASHSCOPE] Task started: {task_id}")

                # Two concurrent tasks: send audio + receive results
                send_task = asyncio.create_task(self._send_audio(ws, task_id))
                recv_task = asyncio.create_task(self._recv_results(ws))

                await asyncio.gather(send_task, recv_task)

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"[ASR DASHSCOPE] WebSocket closed: {e}")
        except Exception as e:
            logger.error(f"[ASR DASHSCOPE] Error: {e}")
            raise

    async def _send_audio(self, ws, task_id: str):
        """Read audio frames from LiveKit and send to DashScope as PCM bytes."""
        async for frame in self._input_ch:
            if isinstance(frame, rtc.AudioFrame):
                # Send raw PCM bytes
                try:
                    await ws.send(frame.data.tobytes())
                except Exception:
                    break

        # Input ended, send finish-task
        try:
            finish_msg = {
                "header": {
                    "action": "finish-task",
                    "task_id": task_id,
                    "streaming": "duplex",
                },
                "payload": {"input": {}},
            }
            await ws.send(json.dumps(finish_msg))
            logger.info(f"[ASR DASHSCOPE] Sent finish-task")
        except Exception:
            pass

    async def _recv_results(self, ws):
        """Receive transcription results and emit SpeechEvents."""
        speech_started = False

        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue  # Ignore binary messages

                data = json.loads(msg)
                event_name = data.get("header", {}).get("event", "")

                if event_name == "result-generated":
                    output = data.get("payload", {}).get("output", {})
                    sentence = output.get("sentence", {})
                    text = sentence.get("text", "")
                    is_end = sentence.get("sentence_end", False)

                    if not text:
                        continue

                    if not speech_started:
                        speech_started = True
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                        )
                        logger.info(f"[ASR START]")

                    if is_end:
                        # Final transcript for this sentence
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                                alternatives=[
                                    stt.SpeechData(language=self._language, text=text, confidence=1.0)
                                ],
                            )
                        )
                        logger.info(f"[ASR FINAL] text=\"{text}\"")

                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH)
                        )
                        speech_started = False
                    else:
                        # Interim result
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                alternatives=[
                                    stt.SpeechData(language=self._language, text=text, confidence=0.8)
                                ],
                            )
                        )
                        logger.info(f"[ASR INTERIM] text=\"{text}\"")

                elif event_name == "task-finished":
                    logger.info(f"[ASR DASHSCOPE] Task finished")
                    break

                elif event_name == "task-failed":
                    err = data.get("header", {}).get("error_message", "unknown")
                    logger.error(f"[ASR DASHSCOPE] Task failed: {err}")
                    break

        except websockets.exceptions.ConnectionClosed:
            pass
