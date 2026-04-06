"""LiveKit audio publisher for voice adversarial testing.

Creates two virtual participants in a LiveKit room (agent + tester),
each with their own audio track. TTS audio is published through these
tracks so a frontend spectator can hear both voices.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from livekit import api, rtc
from livekit.agents import tts

from backend.config import settings

logger = logging.getLogger("sumi.voice_test_audio")

SAMPLE_RATE = 24000
NUM_CHANNELS = 1


class VoiceTestAudioPublisher:
    """Manages two virtual participants publishing TTS audio to a LiveKit room."""

    def __init__(
        self,
        *,
        livekit_url: str = "",
        api_key: str = "",
        api_secret: str = "",
    ):
        self._lk_url = livekit_url or settings.livekit_url
        self._api_key = api_key or settings.livekit_api_key
        self._api_secret = api_secret or settings.livekit_api_secret
        self._lk_api_url = self._lk_url.replace("ws://", "http://").replace("wss://", "https://")

        self._agent_room: rtc.Room | None = None
        self._tester_room: rtc.Room | None = None
        self._agent_source: rtc.AudioSource | None = None
        self._tester_source: rtc.AudioSource | None = None
        self._room_name: str = ""

    async def setup(self) -> dict:
        """Create room + two virtual participants + spectator token.

        Returns dict with: room_name, spectator_token, livekit_url
        """
        self._room_name = f"voicetest_{uuid.uuid4().hex[:12]}"

        # Create room via LiveKit API
        lk_api = api.LiveKitAPI(
            url=self._lk_api_url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        try:
            await lk_api.room.create_room(api.CreateRoomRequest(name=self._room_name))
            logger.info(f"[VOICE-TEST] Room created: {self._room_name}")
        finally:
            await lk_api.aclose()

        # Connect agent participant
        self._agent_room = rtc.Room()
        agent_token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity("voice-test-agent")
            .with_name("Agent")
            .with_grants(api.VideoGrants(room_join=True, room=self._room_name, can_publish=True))
        ).to_jwt()
        await self._agent_room.connect(self._lk_url, agent_token)

        # Connect tester participant
        self._tester_room = rtc.Room()
        tester_token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity("voice-test-tester")
            .with_name("Tester")
            .with_grants(api.VideoGrants(room_join=True, room=self._room_name, can_publish=True))
        ).to_jwt()
        await self._tester_room.connect(self._lk_url, tester_token)

        # Create audio sources and publish tracks
        self._agent_source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        agent_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", self._agent_source)
        await self._agent_room.local_participant.publish_track(
            agent_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        )

        self._tester_source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        tester_track = rtc.LocalAudioTrack.create_audio_track("tester-voice", self._tester_source)
        await self._tester_room.local_participant.publish_track(
            tester_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        )

        # Generate spectator token (subscribe-only)
        spectator_token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(f"spectator-{uuid.uuid4().hex[:8]}")
            .with_name("Spectator")
            .with_grants(api.VideoGrants(
                room_join=True,
                room=self._room_name,
                can_publish=False,
                can_subscribe=True,
            ))
        ).to_jwt()

        logger.info(f"[VOICE-TEST] Both participants connected to {self._room_name}")

        return {
            "room_name": self._room_name,
            "spectator_token": spectator_token,
            "livekit_url": self._lk_url,
        }

    async def publish_audio(self, role: str, tts_plugin: tts.TTS, text: str) -> int:
        """Synthesize TTS and publish audio frames to the room.

        Args:
            role: "agent" or "tester"
            tts_plugin: LiveKit TTS plugin instance
            text: Text to synthesize

        Returns:
            Duration in milliseconds
        """
        source = self._agent_source if role == "agent" else self._tester_source
        if not source:
            raise RuntimeError(f"Audio source for {role} not initialized. Call setup() first.")

        total_samples = 0

        # Use streaming API (works for all TTS providers including CosyVoice)
        stream = tts_plugin.stream()
        stream.push_text(text)
        stream.end_input()

        async for event in stream:
            frame = event.frame
            if frame and frame.data:
                await source.capture_frame(frame)
                total_samples += frame.samples_per_channel
                # Pace to ~real-time to avoid buffer overflow
                frame_duration = frame.samples_per_channel / (frame.sample_rate or SAMPLE_RATE)
                await asyncio.sleep(frame_duration * 0.5)

        # Short silence after speech
        silence_frames = int(0.3 * SAMPLE_RATE)  # 300ms
        silence_data = b"\x00" * (silence_frames * NUM_CHANNELS * 2)
        silence_frame = rtc.AudioFrame(
            data=silence_data,
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            samples_per_channel=silence_frames,
        )
        await source.capture_frame(silence_frame)

        duration_ms = int(total_samples / SAMPLE_RATE * 1000) if total_samples > 0 else 0
        logger.info(f"[VOICE-TEST] {role} audio published: {duration_ms}ms")
        return duration_ms

    async def cleanup(self):
        """Disconnect both virtual participants. Room auto-destroys when empty."""
        for room, name in [(self._agent_room, "agent"), (self._tester_room, "tester")]:
            if room:
                try:
                    await room.disconnect()
                    logger.info(f"[VOICE-TEST] {name} disconnected")
                except Exception as e:
                    logger.warning(f"[VOICE-TEST] {name} disconnect failed: {e}")
        self._agent_room = None
        self._tester_room = None
        self._agent_source = None
        self._tester_source = None
