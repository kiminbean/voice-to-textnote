"""
오디오 분석 스키마
SPEC-AUDIO-ANALYSIS-001: 오디오 품질 분석 독립 엔드포인트
"""

from pydantic import BaseModel, Field


class AudioAnalysisRequest(BaseModel):
    """오디오 분석 요청 (파일 업로드는 엔드포인트에서 직접 처리)"""

    include_silence_detection: bool = Field(
        default=True,
        description="무음 구간 감지 포함 여부",
    )
    silence_threshold_db: float = Field(
        default=-40.0,
        ge=-60.0,
        le=-10.0,
        description="무음 판정 기준 (dBFS, -60 ~ -10)",
    )
    min_silence_duration_ms: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="최소 무음 구간 길이 (ms)",
    )


class SilenceSegment(BaseModel):
    """무음 구간 정보"""

    start_ms: float = Field(description="시작 시점 (ms)")
    end_ms: float = Field(description="종료 시점 (ms)")
    duration_ms: float = Field(description="구간 길이 (ms)")
    avg_dbfs: float | None = Field(default=None, description="평균 볼륨 (dBFS)")


class AudioAnalysisResponse(BaseModel):
    """오디오 분석 결과"""

    filename: str = Field(description="파일명")
    format: str | None = Field(default=None, description="오디오 포맷")
    duration_seconds: float = Field(description="총 재생 시간 (초)")
    sample_rate: int | None = Field(default=None, description="샘플레이트 (Hz)")
    channels: int | None = Field(default=None, description="채널 수")
    sample_width: int | None = Field(default=None, description="샘플 비트 깊이 (bytes)")
    bitrate: str | None = Field(default=None, description="비트레이트")
    file_size_bytes: int = Field(description="파일 크기 (bytes)")

    # 볼륨 분석
    max_dbfs: float | None = Field(default=None, description="최대 볼륨 (dBFS)")
    avg_dbfs: float | None = Field(default=None, description="평균 볼륨 (dBFS)")
    rms_dbfs: float | None = Field(default=None, description="RMS 볼륨 (dBFS)")

    # 무음 구간
    silence_segments: list[SilenceSegment] = Field(
        default_factory=list,
        description="감지된 무음 구간 목록",
    )
    silence_ratio: float | None = Field(
        default=None,
        description="무음 비율 (0.0 ~ 1.0)",
    )
    speech_ratio: float | None = Field(
        default=None,
        description="발화 비율 (0.0 ~ 1.0)",
    )

    # 품질 평가
    quality_score: float | None = Field(
        default=None,
        description="오디오 품질 점수 (0.0 ~ 1.0)",
    )
    quality_issues: list[str] = Field(
        default_factory=list,
        description="감지된 품질 문제 목록",
    )
    recommendation: str | None = Field(
        default=None,
        description="STT 처리를 위한 권장 사항",
    )
