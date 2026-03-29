"""Speaker verification module for voice-based identity gating.

Zero-registration design: the first speech segment automatically becomes the
speaker's anchor embedding. Subsequent segments are compared against it.

Supports multiple embedding models via a common interface:
  - CAM++        (3D-Speaker / ModelScope, ONNX)
  - ERes2NetV2   (3D-Speaker / ModelScope, ONNX)
  - ECAPA-TDNN   (Wespeaker / HuggingFace, ONNX)
  - Resemblyzer  (pip package, lightweight fallback)

Usage:
    verifier = SpeakerVerifier(model="cam++", threshold=0.65)
    is_match, score = verifier.process_audio(pcm_bytes, sample_rate=16000)

Standalone benchmark:
    python -m backend.pipeline.voiceprint --benchmark
"""

from __future__ import annotations

import abc
import hashlib
import logging
import os
import struct
import time
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path(os.environ.get("SUMI_MODEL_CACHE", Path.home() / ".cache" / "sumi" / "models"))

_MODEL_REGISTRY: dict[str, type[EmbeddingModel]] = {}

# ---------------------------------------------------------------------------
# Feature extraction (80-dim log-mel filterbank)
# ---------------------------------------------------------------------------


def _hz_to_mel(hz: np.ndarray) -> np.ndarray:
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _mel_filterbank(sr: int, n_fft: int, n_mels: int) -> np.ndarray:
    """Build a Mel filterbank matrix (n_mels, n_fft // 2 + 1)."""
    low_freq, high_freq = 20.0, sr / 2.0
    low_mel, high_mel = _hz_to_mel(np.array(low_freq)), _hz_to_mel(np.array(high_freq))
    mel_points = np.linspace(low_mel, high_mel, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filters = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        left, center, right = bin_points[i], bin_points[i + 1], bin_points[i + 2]
        for j in range(left, center):
            if center != left:
                filters[i, j] = (j - left) / (center - left)
        for j in range(center, right):
            if right != center:
                filters[i, j] = (right - j) / (right - center)
    return filters


def extract_fbank(
    pcm: np.ndarray,
    sr: int = 16000,
    n_mels: int = 80,
    n_fft: int = 512,
    hop_length: int = 160,
    win_length: int = 400,
) -> np.ndarray:
    """Extract 80-dim log-mel filterbank features from raw PCM (float32, mono).

    Returns array of shape (n_frames, n_mels).
    """
    # Try librosa first for quality, fall back to numpy
    try:
        import librosa  # noqa: F811

        mel = librosa.feature.melspectrogram(
            y=pcm.astype(np.float32),
            sr=sr,
            n_fft=n_fft,
            hop_length=hop_length,
            win_length=win_length,
            n_mels=n_mels,
            fmin=20.0,
            fmax=sr / 2.0,
        )
        log_mel = np.log(np.maximum(mel, 1e-10))
        return log_mel.T.astype(np.float32)  # (T, n_mels)
    except ImportError:
        pass

    # Pure numpy fallback
    # Pre-emphasis
    pcm = pcm.astype(np.float32)
    pcm = np.append(pcm[0], pcm[1:] - 0.97 * pcm[:-1])

    # Framing
    n_samples = len(pcm)
    n_frames = 1 + (n_samples - win_length) // hop_length
    if n_frames < 1:
        # Pad to at least one frame
        pcm = np.pad(pcm, (0, win_length - n_samples))
        n_frames = 1

    frames = np.lib.stride_tricks.as_strided(
        pcm,
        shape=(n_frames, win_length),
        strides=(pcm.strides[0] * hop_length, pcm.strides[0]),
    ).copy()

    # Window
    window = np.hamming(win_length).astype(np.float32)
    frames *= window

    # FFT
    spec = np.fft.rfft(frames, n=n_fft)
    power = np.abs(spec) ** 2

    # Mel filterbank
    mel_fb = _mel_filterbank(sr, n_fft, n_mels)
    mel_spec = power @ mel_fb.T
    log_mel = np.log(np.maximum(mel_spec, 1e-10))

    return log_mel.astype(np.float32)  # (T, n_mels)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    a = a.flatten().astype(np.float64)
    b = b.flatten().astype(np.float64)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm < 1e-12:
        return 0.0
    return float(dot / norm)


# ---------------------------------------------------------------------------
# Model download helpers
# ---------------------------------------------------------------------------


def _download_file(url: str, dest: Path, desc: str = "") -> Path:
    """Download a file with progress logging."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    logger.info(f"Downloading {desc or url} -> {dest}")
    tmp = dest.with_suffix(".tmp")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sumi-voiceprint/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 256
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    if pct % 25 == 0:
                        logger.info(f"  {desc}: {pct}% ({downloaded}/{total})")
        tmp.rename(dest)
        logger.info(f"Downloaded {desc}: {dest} ({dest.stat().st_size} bytes)")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return dest


def _download_modelscope_onnx(model_id: str, filename: str) -> Path:
    """Download an ONNX model from ModelScope."""
    safe_name = model_id.replace("/", "__")
    dest = CACHE_DIR / safe_name / filename
    if dest.exists():
        return dest
    url = f"https://www.modelscope.cn/models/{model_id}/resolve/master/{filename}"
    return _download_file(url, dest, desc=f"ModelScope:{model_id}/{filename}")


def _download_huggingface_file(repo_id: str, filename: str) -> Path:
    """Download a file from HuggingFace."""
    safe_name = repo_id.replace("/", "__")
    dest = CACHE_DIR / safe_name / filename
    if dest.exists():
        return dest
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    return _download_file(url, dest, desc=f"HF:{repo_id}/{filename}")


# ---------------------------------------------------------------------------
# Abstract embedding model
# ---------------------------------------------------------------------------


class EmbeddingModel(abc.ABC):
    """Base class for speaker embedding extractors."""

    name: str = "base"
    embedding_dim: int = 0

    @abc.abstractmethod
    def load(self) -> None:
        """Load the model (download if needed)."""

    @abc.abstractmethod
    def extract(self, pcm: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Extract embedding from PCM audio (float32, mono, 16 kHz).

        Returns 1-D numpy array of shape (embedding_dim,).
        """

    @property
    def is_loaded(self) -> bool:
        return False


def register_model(cls: type[EmbeddingModel]) -> type[EmbeddingModel]:
    """Decorator to register a model class."""
    _MODEL_REGISTRY[cls.name] = cls
    return cls


# ---------------------------------------------------------------------------
# CAM++ (3D-Speaker, ONNX)
# ---------------------------------------------------------------------------


@register_model
class CAMPlusPlusModel(EmbeddingModel):
    name = "cam++"
    embedding_dim = 192

    _MODELSCOPE_ID = "iic/speech_campplus_sv_zh-cn_16k-common"
    _ONNX_FILE = "campplus_cn_common.onnx"

    def __init__(self) -> None:
        self._session = None

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        import onnxruntime as ort

        model_path = _download_modelscope_onnx(self._MODELSCOPE_ID, self._ONNX_FILE)
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        logger.info(f"[voiceprint] Loaded {self.name} from {model_path}")

    def extract(self, pcm: np.ndarray, sr: int = 16000) -> np.ndarray:
        if not self.is_loaded:
            self.load()
        feats = extract_fbank(pcm, sr=sr)  # (T, 80)
        # CMVN: zero-mean, unit-var per feature
        feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-5)
        feats = feats[np.newaxis, :, :]  # (1, T, 80)

        input_name = self._session.get_inputs()[0].name
        output_name = self._session.get_outputs()[0].name
        result = self._session.run([output_name], {input_name: feats.astype(np.float32)})
        emb = result[0].flatten()
        return emb / (np.linalg.norm(emb) + 1e-8)


# ---------------------------------------------------------------------------
# ERes2NetV2 (3D-Speaker, ONNX)
# ---------------------------------------------------------------------------


@register_model
class ERes2NetV2Model(EmbeddingModel):
    name = "eres2netv2"
    embedding_dim = 192

    _MODELSCOPE_ID = "iic/speech_eres2netv2_sv_zh-cn_16k-common"
    _ONNX_FILE = "eres2netv2_cn_common.onnx"

    def __init__(self) -> None:
        self._session = None

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        import onnxruntime as ort

        model_path = _download_modelscope_onnx(self._MODELSCOPE_ID, self._ONNX_FILE)
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        logger.info(f"[voiceprint] Loaded {self.name} from {model_path}")

    def extract(self, pcm: np.ndarray, sr: int = 16000) -> np.ndarray:
        if not self.is_loaded:
            self.load()
        feats = extract_fbank(pcm, sr=sr)
        feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-5)
        feats = feats[np.newaxis, :, :]

        input_name = self._session.get_inputs()[0].name
        output_name = self._session.get_outputs()[0].name
        result = self._session.run([output_name], {input_name: feats.astype(np.float32)})
        emb = result[0].flatten()
        return emb / (np.linalg.norm(emb) + 1e-8)


# ---------------------------------------------------------------------------
# ECAPA-TDNN (Wespeaker, ONNX)
# ---------------------------------------------------------------------------


@register_model
class ECAPATDNNModel(EmbeddingModel):
    name = "ecapa-tdnn"
    embedding_dim = 512

    _HF_REPO = "Wespeaker/wespeaker-ecapa-tdnn512-LM"
    _ONNX_FILE = "model.onnx"

    def __init__(self) -> None:
        self._session = None

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        import onnxruntime as ort

        model_path = _download_huggingface_file(self._HF_REPO, self._ONNX_FILE)
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        logger.info(f"[voiceprint] Loaded {self.name} from {model_path}")

    def extract(self, pcm: np.ndarray, sr: int = 16000) -> np.ndarray:
        if not self.is_loaded:
            self.load()
        feats = extract_fbank(pcm, sr=sr)
        feats = (feats - feats.mean(axis=0)) / (feats.std(axis=0) + 1e-5)
        feats = feats[np.newaxis, :, :]

        input_name = self._session.get_inputs()[0].name
        output_name = self._session.get_outputs()[0].name
        result = self._session.run([output_name], {input_name: feats.astype(np.float32)})
        emb = result[0].flatten()
        return emb / (np.linalg.norm(emb) + 1e-8)


# ---------------------------------------------------------------------------
# Resemblyzer (lightweight fallback)
# ---------------------------------------------------------------------------


@register_model
class ResemblyzerModel(EmbeddingModel):
    name = "resemblyzer"
    embedding_dim = 256

    def __init__(self) -> None:
        self._encoder = None

    @property
    def is_loaded(self) -> bool:
        return self._encoder is not None

    def load(self) -> None:
        from resemblyzer import VoiceEncoder

        self._encoder = VoiceEncoder(device="cpu")
        logger.info(f"[voiceprint] Loaded {self.name}")

    def extract(self, pcm: np.ndarray, sr: int = 16000) -> np.ndarray:
        if not self.is_loaded:
            self.load()
        from resemblyzer import preprocess_wav

        # Resemblyzer expects float32 in [-1, 1], 16 kHz
        wav = preprocess_wav(pcm.astype(np.float32), source_sr=sr)
        emb = self._encoder.embed_utterance(wav)
        return emb / (np.linalg.norm(emb) + 1e-8)


# ---------------------------------------------------------------------------
# Model loader
# ---------------------------------------------------------------------------


def load_model(name: str) -> EmbeddingModel:
    """Instantiate and load a speaker embedding model by name.

    If the requested model fails to load (missing dependencies, download error,
    etc.), falls back through available models and raises only if none work.
    """
    name = name.lower().strip()

    # Try the requested model first
    if name in _MODEL_REGISTRY:
        try:
            model = _MODEL_REGISTRY[name]()
            model.load()
            return model
        except Exception as exc:
            logger.warning(f"[voiceprint] Failed to load '{name}': {exc}")

    # Fallback order
    fallback_order = ["cam++", "eres2netv2", "ecapa-tdnn", "resemblyzer"]
    for fallback_name in fallback_order:
        if fallback_name == name or fallback_name not in _MODEL_REGISTRY:
            continue
        try:
            model = _MODEL_REGISTRY[fallback_name]()
            model.load()
            logger.warning(f"[voiceprint] Fell back from '{name}' to '{fallback_name}'")
            return model
        except Exception as exc:
            logger.warning(f"[voiceprint] Fallback '{fallback_name}' also failed: {exc}")

    raise RuntimeError(
        f"Could not load any speaker embedding model. "
        f"Tried: {name}, {', '.join(f for f in fallback_order if f != name)}. "
        f"Install onnxruntime and/or resemblyzer."
    )


def available_models() -> list[str]:
    """Return names of all registered models."""
    return list(_MODEL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# SpeakerVerifier — main session-level API
# ---------------------------------------------------------------------------


class SpeakerVerifier:
    """Manages speaker verification for a single session.

    Zero-registration: the first speech segment automatically becomes the
    anchor embedding. Subsequent segments are compared against it.

    Integration point: call ``process_audio`` after VAD detects speech, before
    sending to ASR. If ``is_primary_speaker`` is False, skip ASR.
    """

    def __init__(
        self,
        model: str = "cam++",
        threshold: float = 0.65,
        *,
        adaptive: bool = True,
        adaptive_weight: float = 0.1,
    ) -> None:
        self._model: EmbeddingModel = load_model(model)
        self._anchor_embedding: Optional[np.ndarray] = None
        self._threshold = threshold
        self._adaptive = adaptive
        self._adaptive_weight = adaptive_weight
        self._call_count = 0

    @property
    def model_name(self) -> str:
        return self._model.name

    @property
    def embedding_dim(self) -> int:
        return self._model.embedding_dim

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = value

    @property
    def has_anchor(self) -> bool:
        return self._anchor_embedding is not None

    def reset(self) -> None:
        """Clear the anchor embedding, requiring re-enrollment."""
        self._anchor_embedding = None
        self._call_count = 0

    def _pcm_from_bytes(self, pcm_frames: bytes, sample_rate: int) -> np.ndarray:
        """Convert raw PCM bytes (int16 LE) to float32 numpy array."""
        n_samples = len(pcm_frames) // 2
        samples = struct.unpack(f"<{n_samples}h", pcm_frames[:n_samples * 2])
        return np.array(samples, dtype=np.float32) / 32768.0

    def process_audio(
        self,
        pcm_frames: bytes | np.ndarray,
        sample_rate: int = 16000,
    ) -> tuple[bool, float]:
        """Verify whether the audio belongs to the primary speaker.

        Args:
            pcm_frames: Raw PCM audio as bytes (int16 LE) or float32 ndarray.
            sample_rate: Sample rate in Hz (default 16000).

        Returns:
            Tuple of (is_primary_speaker, similarity_score).
            First call always returns (True, 1.0) and sets the anchor.
        """
        if isinstance(pcm_frames, (bytes, bytearray)):
            pcm = self._pcm_from_bytes(pcm_frames, sample_rate)
        else:
            pcm = pcm_frames.astype(np.float32)

        embedding = self._model.extract(pcm, sr=sample_rate)
        self._call_count += 1

        if self._anchor_embedding is None:
            self._anchor_embedding = embedding.copy()
            logger.info(f"[voiceprint] Anchor set (model={self._model.name}, dim={len(embedding)})")
            return True, 1.0

        score = cosine_similarity(embedding, self._anchor_embedding)
        is_match = score >= self._threshold

        # Adaptive anchor update: slowly drift toward confirmed speakers
        if is_match and self._adaptive:
            w = self._adaptive_weight
            self._anchor_embedding = (1 - w) * self._anchor_embedding + w * embedding
            self._anchor_embedding /= np.linalg.norm(self._anchor_embedding) + 1e-8

        return is_match, score

    def process_audio_numpy(
        self,
        pcm: np.ndarray,
        sample_rate: int = 16000,
    ) -> tuple[bool, float]:
        """Convenience alias accepting a numpy array directly."""
        return self.process_audio(pcm, sample_rate)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def run_benchmark(duration_sec: float = 3.0, sample_rate: int = 16000) -> None:
    """Benchmark all available models with synthetic audio."""
    print(f"\n{'='*72}")
    print(f"  Speaker Verification Benchmark — {duration_sec}s audio @ {sample_rate} Hz")
    print(f"{'='*72}\n")

    # Generate test audio: sine wave with some noise (simulates a voice-ish signal)
    t = np.linspace(0, duration_sec, int(duration_sec * sample_rate), dtype=np.float32)
    # Fundamental + harmonics to loosely mimic speech
    pcm_same = (
        0.4 * np.sin(2 * np.pi * 150 * t)
        + 0.2 * np.sin(2 * np.pi * 300 * t)
        + 0.1 * np.sin(2 * np.pi * 450 * t)
        + 0.05 * np.random.randn(len(t)).astype(np.float32)
    )
    # Different "speaker": different fundamental
    pcm_diff = (
        0.4 * np.sin(2 * np.pi * 220 * t)
        + 0.2 * np.sin(2 * np.pi * 440 * t)
        + 0.1 * np.sin(2 * np.pi * 660 * t)
        + 0.05 * np.random.randn(len(t)).astype(np.float32)
    )

    results = []

    for model_name in available_models():
        print(f"--- {model_name} ---")
        try:
            t0 = time.perf_counter()
            model = _MODEL_REGISTRY[model_name]()
            model.load()
            load_time = (time.perf_counter() - t0) * 1000

            # First extraction (anchor)
            t0 = time.perf_counter()
            emb1 = model.extract(pcm_same, sr=sample_rate)
            extract_time_1 = (time.perf_counter() - t0) * 1000

            # Second extraction (same audio)
            t0 = time.perf_counter()
            emb2 = model.extract(pcm_same, sr=sample_rate)
            extract_time_2 = (time.perf_counter() - t0) * 1000

            # Self-similarity
            sim_same = cosine_similarity(emb1, emb2)

            # Different speaker similarity
            t0 = time.perf_counter()
            emb_diff = model.extract(pcm_diff, sr=sample_rate)
            extract_time_diff = (time.perf_counter() - t0) * 1000

            sim_diff = cosine_similarity(emb1, emb_diff)

            print(f"  Load time:       {load_time:8.1f} ms")
            print(f"  Embedding dim:   {len(emb1)}")
            print(f"  Extract (1st):   {extract_time_1:8.1f} ms")
            print(f"  Extract (2nd):   {extract_time_2:8.1f} ms")
            print(f"  Extract (diff):  {extract_time_diff:8.1f} ms")
            print(f"  Same-speaker:    {sim_same:.4f}  (expect ~1.0)")
            print(f"  Diff-speaker:    {sim_diff:.4f}  (expect < threshold)")
            print()

            results.append({
                "model": model_name,
                "dim": len(emb1),
                "load_ms": load_time,
                "extract_ms": extract_time_2,
                "sim_same": sim_same,
                "sim_diff": sim_diff,
            })

        except Exception as exc:
            print(f"  FAILED: {exc}\n")
            results.append({"model": model_name, "error": str(exc)})

    # Summary table
    print(f"\n{'='*72}")
    print(f"  Summary")
    print(f"{'='*72}")
    print(f"  {'Model':<15} {'Dim':>5} {'Load(ms)':>10} {'Infer(ms)':>10} {'Same':>8} {'Diff':>8}")
    print(f"  {'-'*15} {'-'*5} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    for r in results:
        if "error" in r:
            print(f"  {r['model']:<15} {'FAILED':>5} — {r['error']}")
        else:
            print(
                f"  {r['model']:<15} {r['dim']:>5} "
                f"{r['load_ms']:>10.1f} {r['extract_ms']:>10.1f} "
                f"{r['sim_same']:>8.4f} {r['sim_diff']:>8.4f}"
            )
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Speaker verification module")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark on all models")
    parser.add_argument("--model", type=str, default=None, help="Benchmark a specific model only")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    args = parser.parse_args()

    if args.list_models:
        print("Available models:", ", ".join(available_models()))
    elif args.benchmark:
        if args.model:
            # Filter registry to single model
            orig = dict(_MODEL_REGISTRY)
            _MODEL_REGISTRY.clear()
            if args.model in orig:
                _MODEL_REGISTRY[args.model] = orig[args.model]
            else:
                print(f"Unknown model: {args.model}. Available: {', '.join(orig.keys())}")
                exit(1)
            run_benchmark()
            _MODEL_REGISTRY.update(orig)
        else:
            run_benchmark()
    else:
        parser.print_help()
