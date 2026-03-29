"""End-to-end test for the Sumi real-time voice AI agent pipeline.

Tests the full loop: user joins room -> publishes audio -> agent processes
(VAD -> ASR -> NLP -> TTS) -> user receives transcriptions and audio back.

Usage:
    cd /Users/rain/PycharmProjects/sumi.web
    python -m backend.tests.test_e2e

Prerequisites:
    - Backend API running: uvicorn backend.main:app --reload --port 8000
    - Agent worker running: python -m backend.pipeline.worker start
    - LiveKit server running: docker compose up -d
"""

import asyncio
import io
import logging
import os
import struct
import sys
import time
from dataclasses import dataclass, field

import httpx
from livekit import rtc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URL = "http://localhost:8000"
LIVEKIT_URL = "ws://localhost:7880"
AUTH_TOKEN = "dev_user"  # dev mode accepts plain user IDs
AGENT_ID = "default"
AIHUBMIX_KEY = os.environ.get("AIHUBMIX_API_KEY", "")

# Timeouts
ROOM_CREATE_TIMEOUT = 5.0
CONNECT_TIMEOUT = 5.0
AGENT_JOIN_TIMEOUT = 15.0
ASR_TIMEOUT = 15.0
NLP_TIMEOUT = 15.0
TTS_TIMEOUT = 15.0
E2E_TIMEOUT = 30.0

SAMPLE_RATE = 24000
NUM_CHANNELS = 1
# How many samples to push per frame (10ms chunks)
FRAME_DURATION_MS = 20
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_DURATION_MS // 1000

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------


@dataclass
class TestTimings:
    t_start: float = 0.0
    t_room_created: float = 0.0
    t_connected: float = 0.0
    t_audio_publish_start: float = 0.0
    t_audio_publish_end: float = 0.0
    t_agent_joined: float = 0.0
    t_asr_first: float = 0.0
    t_asr_final: float = 0.0
    t_nlp_response: float = 0.0
    t_tts_first_frame: float = 0.0
    t_tts_last_frame: float = 0.0

    asr_text: str = ""
    nlp_text: str = ""
    tts_frames_received: int = 0
    tts_audio_duration_s: float = 0.0
    audio_published_duration_s: float = 0.0


@dataclass
class TestEvents:
    """Async events to coordinate the test flow."""
    agent_joined: asyncio.Event = field(default_factory=asyncio.Event)
    asr_received: asyncio.Event = field(default_factory=asyncio.Event)
    asr_final: asyncio.Event = field(default_factory=asyncio.Event)
    nlp_received: asyncio.Event = field(default_factory=asyncio.Event)
    tts_first_frame: asyncio.Event = field(default_factory=asyncio.Event)
    tts_complete: asyncio.Event = field(default_factory=asyncio.Event)


# ---------------------------------------------------------------------------
# Audio generation
# ---------------------------------------------------------------------------


def generate_tts_audio(text: str) -> bytes:
    """Generate speech audio via AIHubMix TTS API. Returns raw PCM s16le bytes at 24kHz mono."""
    log(None, "Generating TTS audio via AIHubMix...")
    resp = httpx.post(
        "https://aihubmix.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {AIHUBMIX_KEY}"},
        json={
            "model": "tts-1",
            "input": text,
            "voice": "nova",
            "response_format": "pcm",
            "speed": 1.0,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    pcm_bytes = resp.content
    log(None, f"TTS audio generated: {len(pcm_bytes)} bytes "
              f"({len(pcm_bytes) / (SAMPLE_RATE * 2):.1f}s at {SAMPLE_RATE}Hz)")
    return pcm_bytes


def generate_sine_tone(frequency: float = 440.0, duration_s: float = 2.0) -> bytes:
    """Generate a simple sine tone as PCM s16le. Fallback if TTS API is unavailable."""
    import math
    num_samples = int(SAMPLE_RATE * duration_s)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log_start_time: float = 0.0


def log(timings: TestTimings | None, msg: str):
    """Print a timestamped log line."""
    ref = timings.t_start if timings else _log_start_time
    elapsed = time.time() - ref if ref > 0 else 0.0
    print(f"[{elapsed:6.1f}s] {msg}")


# ---------------------------------------------------------------------------
# Room creation via backend API
# ---------------------------------------------------------------------------


async def create_room() -> tuple[str, str, str]:
    """Call backend API to create a room. Returns (room_name, token, livekit_url)."""
    async with httpx.AsyncClient(timeout=ROOM_CREATE_TIMEOUT) as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/rooms/create",
            json={"agent_id": AGENT_ID},
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["room_name"], data["token"], data["livekit_url"]


# ---------------------------------------------------------------------------
# Room cleanup
# ---------------------------------------------------------------------------


async def cleanup_room(room_name: str):
    """Best-effort room deletion via LiveKit API."""
    try:
        from livekit.api import LiveKitAPI, DeleteRoomRequest
        lk_url = LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
        lk_api = LiveKitAPI(url=lk_url, api_key="devkey", api_secret="secret")
        await lk_api.room.delete_room(DeleteRoomRequest(room=room_name))
        await lk_api.aclose()
        log(None, f"Room '{room_name}' deleted")
    except Exception as e:
        log(None, f"Room cleanup failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


async def run_e2e_test() -> bool:
    """Run the full E2E test. Returns True on pass, False on fail."""
    global _log_start_time

    timings = TestTimings()
    events = TestEvents()
    room: rtc.Room | None = None
    room_name: str = ""
    passed = True
    failures: list[str] = []

    print("\n" + "=" * 50)
    print("           E2E Test — Sumi Voice Agent")
    print("=" * 50)

    timings.t_start = time.time()
    _log_start_time = timings.t_start

    try:
        # ------------------------------------------------------------------
        # Step 1: Create room
        # ------------------------------------------------------------------
        room_name, token, livekit_url = await asyncio.wait_for(
            create_room(), timeout=ROOM_CREATE_TIMEOUT
        )
        timings.t_room_created = time.time()
        log(timings, f"Room created: {room_name}")

        # ------------------------------------------------------------------
        # Step 2: Connect to LiveKit
        # ------------------------------------------------------------------
        room = rtc.Room()

        # Set up event handlers before connecting
        _setup_event_handlers(room, timings, events)

        await asyncio.wait_for(
            room.connect(livekit_url, token), timeout=CONNECT_TIMEOUT
        )
        timings.t_connected = time.time()
        log(timings, "Connected to LiveKit")

        # Check if agent is already in the room
        for p in room.remote_participants.values():
            if _is_agent_participant(p):
                timings.t_agent_joined = time.time()
                events.agent_joined.set()
                log(timings, f"Agent already in room: {p.identity}")
                break

        # ------------------------------------------------------------------
        # Step 3: Wait for agent to join
        # ------------------------------------------------------------------
        if not events.agent_joined.is_set():
            log(timings, "Waiting for agent to join...")
            await asyncio.wait_for(
                events.agent_joined.wait(), timeout=AGENT_JOIN_TIMEOUT
            )

        # ------------------------------------------------------------------
        # Step 4: Generate and publish audio
        # ------------------------------------------------------------------
        test_text = "你好，请介绍一下你自己"
        log(timings, f"Preparing test audio: \"{test_text}\"")

        try:
            pcm_bytes = generate_tts_audio(test_text)
        except Exception as e:
            log(timings, f"AIHubMix TTS failed ({e}), falling back to sine tone")
            pcm_bytes = generate_sine_tone(440.0, 2.0)

        # Publish audio track
        source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=NUM_CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("mic", source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(track, options)

        timings.t_audio_publish_start = time.time()
        total_samples = len(pcm_bytes) // 2  # 16-bit = 2 bytes per sample
        timings.audio_published_duration_s = total_samples / SAMPLE_RATE
        log(timings, f"Publishing audio ({timings.audio_published_duration_s:.1f}s of speech)...")

        # Push audio in chunks
        offset = 0
        bytes_per_frame = SAMPLES_PER_FRAME * NUM_CHANNELS * 2  # 2 bytes per s16le sample
        while offset < len(pcm_bytes):
            chunk = pcm_bytes[offset : offset + bytes_per_frame]
            # Pad the last chunk if needed
            if len(chunk) < bytes_per_frame:
                chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))
            frame = rtc.AudioFrame(
                data=chunk,
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=SAMPLES_PER_FRAME,
            )
            await source.capture_frame(frame)
            offset += bytes_per_frame
            # Pace the audio to roughly real-time to trigger VAD properly
            await asyncio.sleep(FRAME_DURATION_MS / 1000.0 * 0.5)

        timings.t_audio_publish_end = time.time()
        log(timings, "Audio publishing complete")

        # Push a short silence to ensure VAD detects end-of-speech
        silence = b"\x00" * bytes_per_frame
        for _ in range(int(0.8 * 1000 / FRAME_DURATION_MS)):  # 800ms silence
            frame = rtc.AudioFrame(
                data=silence,
                sample_rate=SAMPLE_RATE,
                num_channels=NUM_CHANNELS,
                samples_per_channel=SAMPLES_PER_FRAME,
            )
            await source.capture_frame(frame)
            await asyncio.sleep(FRAME_DURATION_MS / 1000.0 * 0.5)

        log(timings, "Silence padding sent (VAD end-of-speech trigger)")

        # ------------------------------------------------------------------
        # Step 5: Wait for ASR result
        # ------------------------------------------------------------------
        log(timings, "Waiting for ASR transcription...")
        try:
            await asyncio.wait_for(events.asr_final.wait(), timeout=ASR_TIMEOUT)
        except asyncio.TimeoutError:
            # If we got partial but no final, still note it
            if events.asr_received.is_set():
                log(timings, "WARNING: Got partial ASR but no final transcript within timeout")
            else:
                log(timings, "WARNING: No ASR transcription received within timeout")

        # ------------------------------------------------------------------
        # Step 6: Wait for NLP response
        # ------------------------------------------------------------------
        if events.asr_final.is_set() or events.asr_received.is_set():
            log(timings, "Waiting for NLP response...")
            try:
                await asyncio.wait_for(events.nlp_received.wait(), timeout=NLP_TIMEOUT)
            except asyncio.TimeoutError:
                log(timings, "WARNING: No NLP response received within timeout")

        # ------------------------------------------------------------------
        # Step 7: Wait for TTS audio
        # ------------------------------------------------------------------
        if events.nlp_received.is_set():
            log(timings, "Waiting for TTS audio...")
            try:
                await asyncio.wait_for(events.tts_first_frame.wait(), timeout=TTS_TIMEOUT)
                # Wait a bit more for TTS to complete
                try:
                    await asyncio.wait_for(events.tts_complete.wait(), timeout=TTS_TIMEOUT)
                except asyncio.TimeoutError:
                    log(timings, "TTS stream did not complete within timeout (partial audio received)")
            except asyncio.TimeoutError:
                log(timings, "WARNING: No TTS audio frames received within timeout")

        # Additional wait for any stragglers
        await asyncio.sleep(1.0)

    except asyncio.TimeoutError as e:
        log(timings, f"TIMEOUT: {e}")
        failures.append(f"Timeout: {e}")
    except Exception as e:
        log(timings, f"ERROR: {type(e).__name__}: {e}")
        failures.append(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # ------------------------------------------------------------------
        # Cleanup
        # ------------------------------------------------------------------
        if room:
            try:
                await room.disconnect()
                log(timings, "Disconnected from LiveKit")
            except Exception:
                pass

        if room_name:
            await cleanup_room(room_name)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("              Latency Report")
    print("=" * 50)

    def delta(a: float, b: float) -> str:
        if a > 0 and b > 0:
            return f"{b - a:.1f}s"
        return "N/A"

    agent_join_latency = delta(timings.t_start, timings.t_agent_joined)
    asr_latency = delta(timings.t_audio_publish_end, timings.t_asr_final)
    nlp_latency = delta(timings.t_asr_final, timings.t_nlp_response)
    tts_latency = delta(timings.t_nlp_response, timings.t_tts_first_frame)
    e2e_total = delta(timings.t_start, timings.t_tts_first_frame)
    e2e_audio = delta(timings.t_audio_publish_start, timings.t_tts_first_frame)

    print(f"  Agent join:     {agent_join_latency}")
    print(f"  ASR latency:    {asr_latency}  (audio end -> final transcript)")
    print(f"  NLP latency:    {nlp_latency}  (ASR final -> NLP response)")
    print(f"  TTS latency:    {tts_latency}  (NLP done -> first audio frame)")
    print(f"  E2E total:      {e2e_total}  (start -> TTS first frame)")
    print(f"  E2E audio:      {e2e_audio}  (audio publish -> TTS first frame)")
    print()
    print(f"  ASR text:       \"{timings.asr_text}\"")
    print(f"  NLP response:   \"{timings.nlp_text[:100]}{'...' if len(timings.nlp_text) > 100 else ''}\"")
    print(f"  TTS frames:     {timings.tts_frames_received}")
    print(f"  TTS duration:   {timings.tts_audio_duration_s:.1f}s")

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("              Assertions")
    print("=" * 50)

    checks = [
        ("Agent joined room", timings.t_agent_joined > 0),
        ("ASR produced text", len(timings.asr_text) > 0),
        ("NLP produced response", len(timings.nlp_text) > 0),
        ("TTS produced audio frames", timings.tts_frames_received > 0),
    ]

    # E2E timing check (generous: 30s from audio start to first TTS frame)
    if timings.t_audio_publish_start > 0 and timings.t_tts_first_frame > 0:
        e2e_seconds = timings.t_tts_first_frame - timings.t_audio_publish_start
        checks.append((f"E2E < 30s (actual: {e2e_seconds:.1f}s)", e2e_seconds < 30.0))

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        marker = " ok " if ok else "FAIL"
        print(f"  [{marker}] {name}")
        if not ok:
            failures.append(name)

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------
    passed = len(failures) == 0
    print("\n" + "=" * 50)
    if passed:
        print("         Result: PASS")
    else:
        print("         Result: FAIL")
        for f in failures:
            print(f"           - {f}")
    print("=" * 50 + "\n")

    return passed


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _is_agent_participant(participant: rtc.RemoteParticipant) -> bool:
    """Heuristic to detect if a remote participant is the agent."""
    identity = participant.identity or ""
    # Agent worker typically has identity starting with "agent-" or containing "agent"
    if "agent" in identity.lower():
        return True
    # Also check if participant has agent kind attribute
    if hasattr(participant, "kind") and participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
        return True
    return False


def _setup_event_handlers(
    room: rtc.Room,
    timings: TestTimings,
    events: TestEvents,
):
    """Wire up all room event handlers for tracking."""

    # Track agent join
    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        log(timings, f"Participant connected: {participant.identity} (kind={getattr(participant, 'kind', 'unknown')})")
        if _is_agent_participant(participant):
            timings.t_agent_joined = time.time()
            events.agent_joined.set()
            log(timings, f"Agent joined room: {participant.identity}")

    # Track transcriptions (both ASR user transcripts and NLP agent responses)
    @room.on("transcription_received")
    def on_transcription(segments, participant, publication):
        now = time.time()
        for seg in segments:
            text = seg.text or ""
            is_final = seg.final
            seg_id = getattr(seg, "id", "")

            # Determine if this is from the user (ASR) or agent (NLP)
            is_agent = False
            if participant:
                identity = getattr(participant, "identity", "")
                is_agent = _is_agent_participant(participant) if isinstance(participant, rtc.RemoteParticipant) else "agent" in identity.lower()

            if is_agent:
                # Agent response (NLP/TTS text)
                if text and not events.nlp_received.is_set():
                    timings.t_nlp_response = now
                    events.nlp_received.set()
                if text:
                    timings.nlp_text += text
                    log(timings, f"[NLP] \"{text}\" (final={is_final})")
            else:
                # User transcription (ASR)
                if text and not events.asr_received.is_set():
                    timings.t_asr_first = now
                    events.asr_received.set()
                if is_final and text:
                    timings.t_asr_final = now
                    timings.asr_text = text
                    events.asr_final.set()
                    log(timings, f"[ASR] \"{text}\" (final)")
                elif text:
                    log(timings, f"[ASR] \"{text}\" (partial)")

    # Track audio from agent (TTS output)
    _tts_frame_count = {"count": 0, "total_samples": 0}
    _tts_silence_task: dict[str, asyncio.Task | None] = {"task": None}

    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if not _is_agent_participant(participant):
            return

        log(timings, f"Subscribed to agent audio track: {track.sid}")
        audio_stream = rtc.AudioStream(track)

        async def _receive_audio():
            async for frame_event in audio_stream:
                audio_frame = frame_event.frame
                _tts_frame_count["count"] += 1
                _tts_frame_count["total_samples"] += audio_frame.samples_per_channel

                timings.tts_frames_received = _tts_frame_count["count"]
                sr = audio_frame.sample_rate or SAMPLE_RATE
                timings.tts_audio_duration_s = _tts_frame_count["total_samples"] / sr

                if not events.tts_first_frame.is_set():
                    timings.t_tts_first_frame = time.time()
                    events.tts_first_frame.set()
                    log(timings, "[TTS] First audio frame received")

                # Reset the silence-detection timer: if no frames for 1.5s, consider TTS complete
                if _tts_silence_task["task"] is not None:
                    _tts_silence_task["task"].cancel()

                async def _mark_complete():
                    await asyncio.sleep(1.5)
                    timings.t_tts_last_frame = time.time()
                    events.tts_complete.set()
                    log(timings, f"[TTS] Audio complete ({timings.tts_audio_duration_s:.1f}s of audio, "
                                 f"{timings.tts_frames_received} frames)")

                _tts_silence_task["task"] = asyncio.create_task(_mark_complete())

        asyncio.create_task(_receive_audio())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    logging.basicConfig(level=logging.WARNING)
    # Suppress noisy loggers
    logging.getLogger("livekit").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        passed = asyncio.run(run_e2e_test())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        passed = False

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
