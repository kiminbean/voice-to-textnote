"""
오디오 청크 분할 및 결과 병합
REQ-STT-018: 30분 초과 오디오 청크 분할 처리
5초 오버랩으로 발화 경계 문제 완화
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydub import AudioSegment

from backend.pipeline.audio_processor import normalize_audio
from backend.schemas.transcription import SegmentResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AudioChunk:
    """분할된 오디오 청크 정보"""

    index: int
    file_path: Path
    start_ms: int  # 원본 오디오 기준 시작 시간 (ms)
    end_ms: int  # 원본 오디오 기준 종료 시간 (ms)
    overlap_ms: int  # 오버랩 길이 (ms)


def split_audio(
    file_path: str | Path,
    chunk_duration_ms: int,
    overlap_ms: int,
    output_dir: str | Path | None = None,
) -> list[AudioChunk]:
    """
    오디오를 chunk_duration_ms 단위로 분할 (overlap_ms 오버랩 포함)
    REQ-STT-018: 30분 단위, 5초 오버랩
    """
    file_path = Path(file_path)
    audio = AudioSegment.from_file(str(file_path))
    total_ms = len(audio)

    if total_ms <= chunk_duration_ms:
        # 청크 분할 불필요
        return []

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[AudioChunk] = []
    chunk_index = 0
    pos_ms = 0

    while pos_ms < total_ms:
        chunk_end_ms = min(pos_ms + chunk_duration_ms + overlap_ms, total_ms)
        chunk_audio = audio[pos_ms:chunk_end_ms]

        # 청크 정규화
        chunk_audio = normalize_audio(chunk_audio)

        chunk_path = output_dir / f"chunk_{chunk_index:04d}.wav"
        chunk_audio.export(str(chunk_path), format="wav")

        chunks.append(
            AudioChunk(
                index=chunk_index,
                file_path=chunk_path,
                start_ms=pos_ms,
                end_ms=chunk_end_ms,
                overlap_ms=overlap_ms if pos_ms > 0 else 0,
            )
        )

        logger.info(
            "청크 생성",
            index=chunk_index,
            start_ms=pos_ms,
            end_ms=chunk_end_ms,
            path=str(chunk_path),
        )

        # 다음 청크 시작 위치 (오버랩 제외)
        pos_ms += chunk_duration_ms
        chunk_index += 1

    return chunks


def merge_segments(
    chunk_results: list[tuple[AudioChunk, list[dict]]],
) -> list[SegmentResult]:
    """
    청크별 전사 결과를 원본 오디오 타임스탬프 기준으로 병합
    오버랩 영역의 중복 세그먼트 제거
    """
    merged: list[SegmentResult] = []
    global_id = 0

    for chunk, raw_segments in chunk_results:
        # 청크 오프셋 (초): 실제 음성 시작 위치
        chunk_offset_sec = chunk.start_ms / 1000.0
        # 오버랩 임계값: 이전 청크에서 이미 처리된 영역
        overlap_threshold_sec = chunk.overlap_ms / 1000.0

        for seg in raw_segments:
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            text = seg.get("text", "").strip()

            if not text:
                continue

            # 오버랩 영역의 첫 청크 이후 세그먼트는 건너뜀 (중복 방지)
            if chunk.index > 0 and seg_start < overlap_threshold_sec:
                continue

            # 원본 타임스탬프로 보정
            adjusted_start = chunk_offset_sec + seg_start
            adjusted_end = chunk_offset_sec + seg_end

            # confidence: mlx-whisper가 avg_logprob을 제공하면 변환, 없으면 0.0
            avg_logprob = seg.get("avg_logprob", None)
            confidence = _logprob_to_confidence(avg_logprob) if avg_logprob is not None else 0.0

            merged.append(
                SegmentResult(
                    id=global_id,
                    start=round(adjusted_start, 3),
                    end=round(adjusted_end, 3),
                    text=text,
                    confidence=round(confidence, 4),
                )
            )
            global_id += 1

    return merged


def _logprob_to_confidence(avg_logprob: float) -> float:
    """
    avg_logprob (음수 값, 범위 [-∞, 0]) → confidence [0, 1] 변환
    whisper 기준: -0.5 이상 = 우수, -1.0 이하 = 불량
    """
    import math

    # exp(avg_logprob)을 클리핑하여 [0, 1] 범위로 변환
    return min(1.0, max(0.0, math.exp(avg_logprob)))
