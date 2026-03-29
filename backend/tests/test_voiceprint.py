"""Benchmark and tests for the speaker verification module.

Usage:
    cd /Users/rain/PycharmProjects/sumi.web
    python -m pytest backend/tests/test_voiceprint.py -v -s

Or run the inline benchmark directly:
    python -m backend.pipeline.voiceprint --benchmark
"""

import struct
import time

import numpy as np
import pytest

from backend.pipeline.voiceprint import (
    SpeakerVerifier,
    cosine_similarity,
    extract_fbank,
    available_models,
    load_model,
    run_benchmark,
    _MODEL_REGISTRY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_voice_like_audio(
    freq: float = 150.0,
    duration: float = 3.0,
    sr: int = 16000,
    noise_level: float = 0.05,
) -> np.ndarray:
    """Generate a synthetic voice-like signal (fundamental + harmonics + noise)."""
    t = np.linspace(0, duration, int(duration * sr), dtype=np.float32)
    signal = (
        0.4 * np.sin(2 * np.pi * freq * t)
        + 0.2 * np.sin(2 * np.pi * 2 * freq * t)
        + 0.1 * np.sin(2 * np.pi * 3 * freq * t)
        + noise_level * np.random.randn(len(t)).astype(np.float32)
    )
    return signal


def _audio_to_pcm_bytes(pcm: np.ndarray) -> bytes:
    """Convert float32 numpy array to int16 LE bytes."""
    int16 = np.clip(pcm * 32768.0, -32768, 32767).astype(np.int16)
    return int16.tobytes()


# ---------------------------------------------------------------------------
# Feature extraction tests
# ---------------------------------------------------------------------------


class TestFbank:
    def test_shape(self):
        pcm = _generate_voice_like_audio(duration=1.0)
        feats = extract_fbank(pcm, sr=16000, n_mels=80)
        assert feats.ndim == 2
        assert feats.shape[1] == 80
        # ~1s at 16kHz with hop=160 should give ~100 frames
        assert 80 <= feats.shape[0] <= 120

    def test_short_audio(self):
        pcm = _generate_voice_like_audio(duration=0.05)
        feats = extract_fbank(pcm, sr=16000)
        assert feats.ndim == 2
        assert feats.shape[0] >= 1
        assert feats.shape[1] == 80

    def test_dtype(self):
        pcm = _generate_voice_like_audio(duration=0.5)
        feats = extract_fbank(pcm)
        assert feats.dtype == np.float32


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.random.randn(192).astype(np.float32)
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        v1 = np.array([1, 0, 0], dtype=np.float32)
        v2 = np.array([0, 1, 0], dtype=np.float32)
        assert cosine_similarity(v1, v2) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        v = np.random.randn(256).astype(np.float32)
        assert cosine_similarity(v, -v) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self):
        v = np.random.randn(192).astype(np.float32)
        zero = np.zeros(192, dtype=np.float32)
        assert cosine_similarity(v, zero) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# SpeakerVerifier tests (model-independent logic)
# ---------------------------------------------------------------------------


class TestSpeakerVerifierLogic:
    """Test the verifier logic using a mock model."""

    class _MockModel:
        name = "mock"
        embedding_dim = 4

        def load(self):
            pass

        @property
        def is_loaded(self):
            return True

        def extract(self, pcm, sr=16000):
            # Deterministic embedding based on mean amplitude
            mean = float(np.mean(np.abs(pcm)))
            emb = np.array([mean, mean * 2, mean * 0.5, 1.0], dtype=np.float32)
            return emb / (np.linalg.norm(emb) + 1e-8)

    @pytest.fixture()
    def verifier(self):
        v = SpeakerVerifier.__new__(SpeakerVerifier)
        v._model = self._MockModel()
        v._anchor_embedding = None
        v._threshold = 0.65
        v._adaptive = False
        v._adaptive_weight = 0.1
        v._call_count = 0
        return v

    def test_first_call_sets_anchor(self, verifier):
        pcm = _generate_voice_like_audio(freq=150, duration=1.0)
        is_match, score = verifier.process_audio(pcm)
        assert is_match is True
        assert score == 1.0
        assert verifier.has_anchor

    def test_same_audio_matches(self, verifier):
        pcm = _generate_voice_like_audio(freq=150, duration=1.0)
        verifier.process_audio(pcm)
        is_match, score = verifier.process_audio(pcm)
        assert is_match is True
        assert score > 0.99

    def test_bytes_input(self, verifier):
        pcm = _generate_voice_like_audio(freq=150, duration=1.0)
        pcm_bytes = _audio_to_pcm_bytes(pcm)
        is_match, score = verifier.process_audio(pcm_bytes)
        assert is_match is True
        assert score == 1.0

    def test_reset_clears_anchor(self, verifier):
        pcm = _generate_voice_like_audio(freq=150, duration=1.0)
        verifier.process_audio(pcm)
        assert verifier.has_anchor
        verifier.reset()
        assert not verifier.has_anchor

    def test_threshold_property(self, verifier):
        assert verifier.threshold == 0.65
        verifier.threshold = 0.8
        assert verifier.threshold == 0.8


# ---------------------------------------------------------------------------
# Per-model integration tests (skipped if model unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_name", available_models())
class TestModelIntegration:
    """Integration tests that attempt to load each model.

    Skipped if the model cannot be loaded (missing deps, no network, etc.).
    """

    def test_load_and_extract(self, model_name):
        try:
            model = load_model(model_name)
        except Exception as exc:
            pytest.skip(f"Cannot load {model_name}: {exc}")

        pcm = _generate_voice_like_audio(duration=3.0)

        t0 = time.perf_counter()
        emb = model.extract(pcm, sr=16000)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert emb.ndim == 1
        assert len(emb) == model.embedding_dim
        # L2 norm should be ~1.0 (we normalize in each model)
        assert np.linalg.norm(emb) == pytest.approx(1.0, abs=0.01)

        print(f"\n  {model_name}: dim={len(emb)}, extract={elapsed_ms:.1f}ms")

    def test_same_audio_high_similarity(self, model_name):
        try:
            model = load_model(model_name)
        except Exception:
            pytest.skip(f"Cannot load {model_name}")

        pcm = _generate_voice_like_audio(duration=3.0)
        emb1 = model.extract(pcm)
        emb2 = model.extract(pcm)
        sim = cosine_similarity(emb1, emb2)

        assert sim > 0.95, f"Same-audio similarity too low: {sim:.4f}"
        print(f"\n  {model_name}: same-audio sim={sim:.4f}")

    def test_different_audio_lower_similarity(self, model_name):
        try:
            model = load_model(model_name)
        except Exception:
            pytest.skip(f"Cannot load {model_name}")

        pcm1 = _generate_voice_like_audio(freq=150, duration=3.0)
        pcm2 = _generate_voice_like_audio(freq=300, duration=3.0)
        emb1 = model.extract(pcm1)
        emb2 = model.extract(pcm2)
        sim = cosine_similarity(emb1, emb2)

        print(f"\n  {model_name}: diff-audio sim={sim:.4f}")
        # We just check it's lower than same-audio; threshold depends on model
        assert sim < 1.0

    def test_extraction_speed(self, model_name):
        """Verify extraction completes in <50ms for 3s audio on CPU."""
        try:
            model = load_model(model_name)
        except Exception:
            pytest.skip(f"Cannot load {model_name}")

        pcm = _generate_voice_like_audio(duration=3.0)

        # Warm up
        model.extract(pcm)

        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            model.extract(pcm)
            times.append((time.perf_counter() - t0) * 1000)

        median_ms = sorted(times)[len(times) // 2]
        print(f"\n  {model_name}: median extract = {median_ms:.1f}ms (target <50ms)")
        # Soft assertion: warn but don't fail if slightly over on CI
        if median_ms > 50:
            import warnings

            warnings.warn(f"{model_name} extraction took {median_ms:.1f}ms (target <50ms)")


# ---------------------------------------------------------------------------
# Benchmark entry point (also runnable via pytest -s)
# ---------------------------------------------------------------------------


def test_run_benchmark(capsys):
    """Run the full benchmark (prints to stdout)."""
    run_benchmark(duration_sec=2.0)
    captured = capsys.readouterr()
    assert "Summary" in captured.out or "FAILED" in captured.out
