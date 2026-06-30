"""Speaker voiceprint embedding extraction.

The preferred backend is pyannote's speaker embedding model when available.
If the model/token is unavailable, a deterministic local acoustic embedding is
used so enrollment and matching still work in local/offline deployments.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from threading import Lock
from typing import Any

from backend.app.config import settings
from backend.pipeline.speaker_matcher import SpeakerSegment
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SpeakerEmbeddingEngine:
    """Extract fixed-length voiceprint embeddings from speaker audio segments."""

    _instance: SpeakerEmbeddingEngine | None = None
    _lock = Lock()
    _pyannote_model: Any = None
    _pyannote_inference: Any = None
    _pyannote_available: bool | None = None

    @classmethod
    def get_instance(cls) -> SpeakerEmbeddingEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def extract_for_speakers(
        self,
        audio_path: str | Path,
        speaker_segments: list[SpeakerSegment],
        *,
        max_seconds_per_speaker: float = 30.0,
        min_seconds_per_speaker: float = 0.0,
    ) -> dict[str, dict[str, Any]]:
        """Return voiceprint data keyed by diarization speaker id."""
        grouped: dict[str, list[SpeakerSegment]] = {}
        for segment in speaker_segments:
            if not segment.speaker_id:
                continue
            grouped.setdefault(segment.speaker_id, []).append(segment)

        result: dict[str, dict[str, Any]] = {}
        for speaker_id, segments in grouped.items():
            sample_duration = sum(max(0.0, seg.end - seg.start) for seg in segments)
            if sample_duration < min_seconds_per_speaker:
                logger.info(
                    "voiceprint extraction skipped: not enough speech",
                    speaker_id=speaker_id,
                    sample_duration_seconds=round(sample_duration, 3),
                    min_seconds_per_speaker=min_seconds_per_speaker,
                    category="voiceprint",
                )
                continue
            embedding, backend = self.extract_embedding(
                audio_path,
                segments,
                max_seconds=max_seconds_per_speaker,
            )
            if embedding:
                result[speaker_id] = {
                    "speaker_id": speaker_id,
                    "embedding": embedding,
                    "embedding_backend": backend,
                    "sample_duration_seconds": round(sample_duration, 3),
                }
        return result

    def extract_embedding(
        self,
        audio_path: str | Path,
        segments: list[SpeakerSegment],
        *,
        max_seconds: float = 30.0,
    ) -> tuple[list[float], str]:
        """Extract one embedding from the given speaker segments."""
        path = Path(audio_path)
        if not path.exists() or not segments:
            return [], "none"

        try:
            embedding = self._extract_pyannote(path, segments, max_seconds=max_seconds)
            if embedding:
                return embedding, "pyannote"
        except Exception:
            logger.warning(
                "pyannote speaker embedding failed; falling back to acoustic embedding",
                audio_path=str(path),
                exc_info=True,
                category="voiceprint",
            )

        return self._extract_acoustic(path, segments, max_seconds=max_seconds), "acoustic"

    def _load_pyannote(self) -> Any:
        if self._pyannote_available is False:
            return None
        if self._pyannote_inference is not None:
            return self._pyannote_inference

        with self._lock:
            if self._pyannote_inference is not None:
                return self._pyannote_inference
            try:
                from pyannote.audio import Inference, Model  # type: ignore[import]

                model_name = getattr(settings, "speaker_embedding_model", "pyannote/embedding")
                token = settings.huggingface_token or None
                start = time.time()
                model = Model.from_pretrained(model_name, token=token)
                self._pyannote_model = model
                self._pyannote_inference = Inference(model, window="whole")
                self._pyannote_available = True
                logger.info(
                    "speaker embedding model loaded",
                    model=model_name,
                    load_time_seconds=round(time.time() - start, 2),
                )
            except Exception:
                self._pyannote_available = False
                logger.warning(
                    "speaker embedding model unavailable; acoustic fallback enabled",
                    exc_info=True,
                    category="voiceprint",
                )
                return None
        return self._pyannote_inference

    def _extract_pyannote(
        self,
        audio_path: Path,
        segments: list[SpeakerSegment],
        *,
        max_seconds: float,
    ) -> list[float]:
        inference = self._load_pyannote()
        if inference is None:
            return []

        from pyannote.core import Segment  # type: ignore[import]

        vectors: list[list[float]] = []
        consumed = 0.0
        for segment in sorted(segments, key=lambda s: s.end - s.start, reverse=True):
            duration = max(0.0, segment.end - segment.start)
            if duration <= 0.2:
                continue
            end = segment.end
            if consumed + duration > max_seconds:
                end = segment.start + max(0.2, max_seconds - consumed)
                duration = max(0.0, end - segment.start)
            if duration <= 0.2:
                break
            raw = inference.crop(str(audio_path), Segment(segment.start, end))
            vector = _flatten_numeric(raw)
            if vector:
                vectors.append(vector)
                consumed += duration
            if consumed >= max_seconds:
                break

        return _mean_normalized(vectors)

    def _extract_acoustic(
        self,
        audio_path: Path,
        segments: list[SpeakerSegment],
        *,
        max_seconds: float,
    ) -> list[float]:
        import torch
        import torchaudio

        waveform, sample_rate = torchaudio.load(str(audio_path))
        if waveform.dim() > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if sample_rate != 16000:
            waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
            sample_rate = 16000

        chunks = []
        consumed = 0.0
        for segment in sorted(segments, key=lambda s: s.end - s.start, reverse=True):
            if consumed >= max_seconds:
                break
            start = max(0, int(segment.start * sample_rate))
            end = min(waveform.shape[-1], int(segment.end * sample_rate))
            if end <= start:
                continue
            max_len = int((max_seconds - consumed) * sample_rate)
            chunk = waveform[:, start : min(end, start + max_len)]
            if chunk.shape[-1] < int(0.2 * sample_rate):
                continue
            chunks.append(chunk)
            consumed += chunk.shape[-1] / sample_rate

        if not chunks:
            return []

        audio = torch.cat(chunks, dim=-1).squeeze(0).float()
        if audio.numel() == 0:
            return []
        audio = audio - audio.mean()
        peak = audio.abs().max()
        if peak > 0:
            audio = audio / peak

        mfcc = torchaudio.transforms.MFCC(
            sample_rate=sample_rate,
            n_mfcc=20,
            melkwargs={"n_fft": 400, "hop_length": 160, "n_mels": 40},
        )(audio.unsqueeze(0)).squeeze(0)
        mfcc_mean = mfcc.mean(dim=-1)
        mfcc_std = mfcc.std(dim=-1)

        frame_length = int(0.025 * sample_rate)
        hop_length = int(0.010 * sample_rate)
        frames = audio.unfold(0, frame_length, hop_length)
        rms = torch.sqrt(torch.mean(frames * frames, dim=1) + 1e-9)
        zcr = torch.mean((frames[:, 1:] * frames[:, :-1] < 0).float(), dim=1)

        spec = torch.fft.rfft(frames * torch.hann_window(frame_length), dim=1).abs()
        freqs = torch.linspace(0, sample_rate / 2, spec.shape[1])
        centroid = (spec * freqs).sum(dim=1) / (spec.sum(dim=1) + 1e-9)
        bandwidth = torch.sqrt(
            (spec * (freqs.unsqueeze(0) - centroid.unsqueeze(1)).pow(2)).sum(dim=1)
            / (spec.sum(dim=1) + 1e-9)
        )

        features = torch.cat(
            [
                mfcc_mean,
                mfcc_std,
                torch.tensor(
                    [
                        float(rms.mean()),
                        float(rms.std()),
                        float(zcr.mean()),
                        float(zcr.std()),
                        float(centroid.mean() / (sample_rate / 2)),
                        float(centroid.std() / (sample_rate / 2)),
                        float(bandwidth.mean() / (sample_rate / 2)),
                        float(bandwidth.std() / (sample_rate / 2)),
                    ]
                ),
            ]
        )
        return _normalize([float(x) for x in features])


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _flatten_numeric(value: Any) -> list[float]:
    try:
        import numpy as np

        array = np.asarray(value, dtype=float).reshape(-1)
        return [float(x) for x in array if math.isfinite(float(x))]
    except Exception:
        if isinstance(value, list | tuple):
            result: list[float] = []
            for item in value:
                result.extend(_flatten_numeric(item))
            return result
        try:
            number = float(value)
        except Exception:
            return []
        return [number] if math.isfinite(number) else []


def _mean_normalized(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = min(len(v) for v in vectors)
    if width <= 0:
        return []
    mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(width)]
    return _normalize(mean)


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 0:
        return []
    return [round(v / norm, 8) for v in values]
