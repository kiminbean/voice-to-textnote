"""
오디오 품질 분석 엔진
SPEC-AUDIO-ANALYSIS-001: 오디오 파일 품질 분석, 무음 구간 감지, STT 적합성 평가
"""

import math
from dataclasses import dataclass
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SilenceSegment:
    start_ms: float
    end_ms: float
    duration_ms: float
    avg_dbfs: float | None = None


@dataclass
class AudioAnalysisResult:
    filename: str
    format: str | None
    duration_seconds: float
    sample_rate: int | None
    channels: int | None
    sample_width: int | None
    bitrate: str | None
    file_size_bytes: int
    max_dbfs: float | None
    avg_dbfs: float | None
    rms_dbfs: float | None
    silence_segments: list[SilenceSegment]
    silence_ratio: float | None
    speech_ratio: float | None
    quality_score: float | None
    quality_issues: list[str]
    recommendation: str | None


def analyze_audio(
    file_path: str | Path,
    include_silence_detection: bool = True,
    silence_threshold_db: float = -40.0,
    min_silence_duration_ms: int = 500,
) -> AudioAnalysisResult:
    """
    오디오 파일 품질 분석

    Args:
        file_path: 오디오 파일 경로
        include_silence_detection: 무음 구간 감지 여부
        silence_threshold_db: 무음 판정 기준 (dBFS)
        min_silence_duration_ms: 최소 무음 구간 길이 (ms)

    Returns:
        AudioAnalysisResult
    """
    from pydub import AudioSegment
    from pydub.utils import mediainfo

    file_path = Path(file_path)
    file_size = file_path.stat().st_size

    try:
        audio = AudioSegment.from_file(str(file_path))
    except Exception as e:
        raise ValueError(f"오디오 파일 로드 실패: {e}") from e

    duration_seconds = len(audio) / 1000.0
    sample_rate = audio.frame_rate
    channels = audio.channels
    sample_width = audio.sample_width

    # 포맷/비트레이트 정보
    format_info = file_path.suffix.lstrip(".").upper()
    bitrate = None
    try:
        info = mediainfo(str(file_path))
        bitrate = info.get("bit_rate")
        if bitrate:
            bitrate = f"{int(bitrate) // 1000} kbps"
    except Exception:  # pragma: no cover
        pass

    # 볼륨 분석
    max_dbfs = audio.max_dBFS
    avg_dbfs = audio.dBFS
    # RMS 계산
    rms = audio.rms
    max_possible_amplitude = float(1 << (8 * sample_width - 1))
    rms_dbfs = 20 * math.log10(rms / max_possible_amplitude) if rms > 0 else -float("inf")

    # 무음 구간 감지
    silence_segments: list[SilenceSegment] = []
    silence_ratio = None
    speech_ratio = None

    if include_silence_detection and duration_seconds > 0:
        silence_segments = _detect_silence(
            audio,
            threshold_db=silence_threshold_db,
            min_duration_ms=min_silence_duration_ms,
        )

        total_silence_ms = sum(s.duration_ms for s in silence_segments)
        total_duration_ms = len(audio)
        silence_ratio = (
            round(total_silence_ms / total_duration_ms, 3) if total_duration_ms > 0 else 0.0
        )
        speech_ratio = round(1.0 - silence_ratio, 3)

    # 품질 평가
    quality_score, quality_issues, recommendation = _evaluate_quality(
        audio=audio,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        avg_dbfs=avg_dbfs,
        silence_ratio=silence_ratio,
    )

    return AudioAnalysisResult(
        filename=file_path.name,
        format=format_info,
        duration_seconds=round(duration_seconds, 2),
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        bitrate=bitrate,
        file_size_bytes=file_size,
        max_dbfs=round(max_dbfs, 2) if max_dbfs != -float("inf") else None,
        avg_dbfs=round(avg_dbfs, 2) if avg_dbfs != -float("inf") else None,
        rms_dbfs=round(rms_dbfs, 2) if rms_dbfs != -float("inf") else None,
        silence_segments=silence_segments,
        silence_ratio=silence_ratio,
        speech_ratio=speech_ratio,
        quality_score=quality_score,
        quality_issues=quality_issues,
        recommendation=recommendation,
    )


def _detect_silence(
    audio,
    threshold_db: float = -40.0,
    min_duration_ms: int = 500,
) -> list[SilenceSegment]:
    """무음 구간 감지"""
    from pydub.silence import detect_silence as pydub_detect_silence

    try:
        raw_silences = pydub_detect_silence(
            audio,
            min_silence_len=min_duration_ms,
            silence_thresh=threshold_db,
        )
    except Exception as e:
        logger.warning("무음 감지 실패", error=str(e))
        return []

    segments = []
    for start_ms, end_ms in raw_silences:
        duration = end_ms - start_ms
        # 해당 구간 평균 볼륨
        segment = audio[start_ms:end_ms]
        seg_dbfs = segment.dBFS if segment.dBFS != -float("inf") else None

        segments.append(
            SilenceSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=duration,
                avg_dbfs=round(seg_dbfs, 2) if seg_dbfs is not None else None,
            )
        )

    return segments


def _evaluate_quality(
    audio,
    duration_seconds: float,
    sample_rate: int,
    channels: int,
    avg_dbfs: float,
    silence_ratio: float | None,
) -> tuple[float, list[str], str]:
    """
    오디오 품질 평가

    Returns:
        (quality_score, issues, recommendation)
    """
    issues: list[str] = []
    score = 1.0

    # 1. 볼륨 레벨 검사
    if avg_dbfs < -30:
        issues.append(f"볼륨이 매우 낮습니다 (평균 {avg_dbfs:.1f} dBFS)")
        score -= 0.2  # pragma: no cover
    elif avg_dbfs < -20:
        issues.append(f"볼륨이 다소 낮습니다 (평균 {avg_dbfs:.1f} dBFS)")  # pragma: no cover
        score -= 0.1  # pragma: no cover
    elif avg_dbfs > -3:
        issues.append("볼륨이 너무 높습니다 (클리핑 가능성)")
        score -= 0.15

    # 2. 샘플레이트 검사
    if sample_rate < 8000:
        issues.append(
            f"샘플레이트가 너무 낮아 STT 품질이 크게 저하될 수 있습니다 ({sample_rate}Hz)"
        )
        score -= 0.4
    elif sample_rate < 16000:
        issues.append(f"샘플레이트가 낮습니다 ({sample_rate}Hz, 권장: 16kHz 이상)")
        score -= 0.2

    # 3. 채널 수
    if channels > 2:
        issues.append(
            f"채널 수가 많습니다 ({channels}ch). 다중 화자 환경에서 화자 분리가 어려울 수 있습니다."
        )
        score -= 0.1

    # 4. 녹음 길이
    if duration_seconds < 5:
        issues.append("녹음이 너무 짧습니다 (5초 미만)")
        score -= 0.1

    # 5. 무음 비율
    if silence_ratio is not None:
        if silence_ratio > 0.7:
            issues.append(
                f"무음 비율이 높습니다 ({silence_ratio * 100:.0f}%). 실제 발화 내용이 적습니다."
            )
            score -= 0.15  # pragma: no cover
        elif silence_ratio > 0.5:
            issues.append(
                f"무음 비율이 다소 높습니다 ({silence_ratio * 100:.0f}%)"
            )  # pragma: no cover
            score -= 0.05  # pragma: no cover

    # 점수 보정 (0.0 ~ 1.0)
    score = max(0.0, min(1.0, score))

    # 권장 사항
    if score >= 0.8:
        recommendation = "STT 처리에 적합한 오디오 품질입니다."
    elif score >= 0.5:
        recommendation = "STT 처리 가능하지만, 전처리(볼륨 정규화 등)를 권장합니다."
    else:
        recommendation = (
            "오디오 품질이 낮아 STT 정확도가 크게 저하될 수 있습니다. 녹음 환경 개선을 권장합니다."
        )

    return round(score, 2), issues, recommendation
