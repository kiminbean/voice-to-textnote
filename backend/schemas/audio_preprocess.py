"""
SPEC-AUDIO-PREP-001: 오디오 전처리 API 스키마 (Pydantic v2).

POST /api/v1/audio/preprocess
- multipart/form-data로 오디오 + 옵션 전달
- 처리된 WAV 파일 다운로드 응답

여기서는 응답/메타데이터 스키마만 정의합니다.
요청은 multipart Form 필드로 받기 때문에 라우터에서 직접 처리합니다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PreprocessOptionsPayload(BaseModel):
    """라우터 Form 필드에서 변환된 옵션을 표현하는 검증용 모델.

    실제 API는 multipart Form 필드를 사용하지만, 통합 테스트와 내부
    프로그램적 호출을 위해 동일한 스키마를 JSON으로도 사용할 수 있게 둔다.
    """

    convert_to_16k_mono: bool = Field(default=True, description="16kHz 모노 WAV로 강제 변환")
    normalize: bool = Field(default=True, description="dBFS 정규화 적용 여부")
    target_dbfs: float = Field(
        default=-20.0,
        ge=-60.0,
        le=0.0,
        description="정규화 목표 레벨(dBFS)",
    )
    high_pass_hz: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="이 주파수 미만 차단 (저주파 험·팬 노이즈 제거)",
    )
    low_pass_hz: int | None = Field(
        default=None,
        ge=1000,
        le=16000,
        description="이 주파수 초과 차단 (고주파 화이트노이즈 완화)",
    )
    trim_silence: bool = Field(default=False, description="앞/뒤 무음 구간 자동 제거")
    silence_threshold_db: float = Field(
        default=-40.0,
        ge=-80.0,
        le=-10.0,
        description="이 dBFS 아래는 무음으로 간주",
    )
    silence_min_len_ms: int = Field(
        default=700,
        ge=100,
        le=10_000,
        description="이 길이 이상 연속 무음만 트리밍 대상",
    )


class PreprocessResultMetadata(BaseModel):
    """전처리 응답 헤더로 함께 내려가는 메타데이터.

    실제 응답 body는 WAV 바이너리이므로, 메타데이터는
    응답 헤더 `X-Audio-Preprocess-Meta`에 JSON으로 직렬화되어 전달됩니다.
    """

    original_filename: str
    original_size_bytes: int
    processed_size_bytes: int
    duration_seconds: float
    sample_rate: int
    channels: int
    applied: PreprocessOptionsPayload
