"""DashScope CosyVoice TTS adapter for LiveKit Agents.

Streams text to Alibaba's CosyVoice via WebSocket, receives audio chunks.
"""

import asyncio
import json
import logging
import uuid

import websockets
from livekit.agents import tts, APIConnectOptions

from backend.config import settings

DEFAULT_CONN = APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=10.0)

logger = logging.getLogger(__name__)


class CosyVoiceTTS(tts.TTS):
    def __init__(
        self,
        *,
        model: str = "cosyvoice-v3-flash",
        voice: str = "longanyang",
        sample_rate: int = 22050,
        audio_format: str = "pcm",
        api_key: str = "",
        ws_url: str = "",
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._model = model
        self._voice = voice
        self._audio_format = audio_format
        self._api_key = api_key or settings.dashscope_api_key
        self._ws_url = ws_url or settings.dashscope_ws_url

    def synthesize(self, text, *, conn_options=DEFAULT_CONN):
        raise NotImplementedError("Use stream() for CosyVoice — it's streaming-only")

    def stream(self, *, conn_options=DEFAULT_CONN):
        return CosyVoiceSynthesizeStream(
            tts=self,
            conn_options=conn_options,
            model=self._model,
            voice=self._voice,
            sample_rate=self._sample_rate,
            audio_format=self._audio_format,
            api_key=self._api_key,
            ws_url=self._ws_url,
        )


class CosyVoiceSynthesizeStream(tts.SynthesizeStream):
    def __init__(self, *, tts, conn_options=DEFAULT_CONN, model, voice, sample_rate, audio_format, api_key, ws_url, **kwargs):
        super().__init__(tts=tts, conn_options=conn_options)
        self._model = model
        self._voice = voice
        self._sample_rate = sample_rate
        self._audio_format = audio_format
        self._api_key = api_key
        self._ws_url = ws_url

    async def _run(self, output_emitter: tts.AudioEmitter):
        """Connect to CosyVoice WebSocket, send text, receive audio."""
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
                logger.info(f"[TTS COSYVOICE] Connected, model={self._model}, voice={self._voice}")

                # Send run-task
                run_task = {
                    "header": {
                        "action": "run-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {
                        "task_group": "audio",
                        "task": "tts",
                        "function": "SpeechSynthesizer",
                        "model": self._model,
                        "parameters": {
                            "voice": self._voice,
                            "format": self._audio_format,
                            "sample_rate": self._sample_rate,
                        },
                        "input": {},
                    },
                }
                await ws.send(json.dumps(run_task))

                # Wait for task-started
                resp = json.loads(await ws.recv())
                event_name = resp.get("header", {}).get("event", "")
                if event_name != "task-started":
                    err = resp.get("header", {}).get("error_message", event_name)
                    raise Exception(f"CosyVoice task failed: {err}")

                logger.info(f"[TTS COSYVOICE] Task started: {task_id}")

                # Initialize output
                mime = "audio/pcm" if self._audio_format == "pcm" else f"audio/{self._audio_format}"
                output_emitter.initialize(
                    request_id=task_id,
                    sample_rate=self._sample_rate,
                    num_channels=1,
                    mime_type=mime,
                    stream=True,
                )
                output_emitter.start_segment(segment_id=uuid.uuid4().hex)

                # Send text + receive audio concurrently
                send_task = asyncio.create_task(self._send_text(ws, task_id))
                recv_task = asyncio.create_task(self._recv_audio(ws, output_emitter))

                await asyncio.gather(send_task, recv_task)

                output_emitter.end_segment()

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"[TTS COSYVOICE] WebSocket closed: {e}")
        except Exception as e:
            logger.error(f"[TTS COSYVOICE] Error: {e}")
            raise

    async def _send_text(self, ws, task_id: str):
        """Read text tokens from LiveKit and send to CosyVoice."""
        text_buffer = ""

        async for token in self._input_ch:
            if isinstance(token, str):
                text_buffer += token

                # Send on sentence boundaries or when buffer is big enough
                if text_buffer and (
                    text_buffer[-1] in "。！？.!?\n，,、；;" or len(text_buffer) > 60
                ):
                    continue_msg = {
                        "header": {
                            "action": "continue-task",
                            "task_id": task_id,
                            "streaming": "duplex",
                        },
                        "payload": {
                            "input": {"text": text_buffer},
                        },
                    }
                    try:
                        await ws.send(json.dumps(continue_msg))
                        logger.debug(f"[TTS COSYVOICE] Sent text: {text_buffer[:50]}")
                    except Exception:
                        break
                    text_buffer = ""

        # Flush remaining text
        if text_buffer.strip():
            try:
                continue_msg = {
                    "header": {
                        "action": "continue-task",
                        "task_id": task_id,
                        "streaming": "duplex",
                    },
                    "payload": {"input": {"text": text_buffer}},
                }
                await ws.send(json.dumps(continue_msg))
            except Exception:
                pass

        # Send finish-task
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
            logger.info(f"[TTS COSYVOICE] Sent finish-task")
        except Exception:
            pass

    async def _recv_audio(self, ws, output_emitter: tts.AudioEmitter):
        """Receive audio chunks from CosyVoice and push to output."""
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    # Audio data
                    output_emitter.push(msg)
                elif isinstance(msg, str):
                    data = json.loads(msg)
                    event_name = data.get("header", {}).get("event", "")

                    if event_name == "task-finished":
                        logger.info(f"[TTS COSYVOICE] Task finished")
                        break
                    elif event_name == "task-failed":
                        err = data.get("header", {}).get("error_message", "unknown")
                        logger.error(f"[TTS COSYVOICE] Failed: {err}")
                        break
        except websockets.exceptions.ConnectionClosed:
            pass
