"""
회의록 생성 요청/응답 Pydantic v2 스키마
REQ-MIN-001~005 관련
"""

from pydantic import BaseModel, Field

from backend.schemas.transcription import TaskStatus


class MinutesCreateRequest(BaseModel):
    """POST /api/v1/minutes 요청 본문"""

    # 화자 분리 결과 참조 ID (필수)
    diarization_task_id: str = Field(..., description="화자 분리 작업 ID")
    # 출력 형식: json 또는 markdown (기본값: json)
    output_format: str = Field(default="json", description="출력 형식 (json 또는 markdown)")
    # 화자 이름 매핑 (REQ-MIN-017): {"SPEAKER_00": "김팀장"}
    speaker_names: dict[str, str] | None = Field(
        default=None, description="화자 ID → 이름 매핑 (None이면 자동 생성)"
    )


class MinutesSegment(BaseModel):
    """회의록 개별 세그먼트"""

    # speaker_id=None 허용 (REQ-MIN-005: Unknown Speaker)
    speaker_id: str | None = Field(default=None, description="화자 ID (None=알 수 없음)")
    speaker_name: str = Field(..., description="화자 표시 이름")
    text: str = Field(..., description="발화 텍스트")
    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")


class SpeakerStats(BaseModel):
    """화자별 통계 (REQ-MIN-002)"""

    speaker_id: str = Field(..., description="화자 ID")
    speaker_name: str = Field(..., description="화자 표시 이름")
    total_speaking_time: float = Field(..., description="총 발화 시간 (초)")
    segment_count: int = Field(..., description="발화 세그먼트 수")
    # speaking_ratio: 전체 대화 시간 대비 발화 비율 (%)
    speaking_ratio: float = Field(..., description="발화 비율 (%)")


class MinutesResponse(BaseModel):
    """GET /api/v1/minutes/{task_id} 응답"""

    task_id: str = Field(..., description="회의록 작업 ID")
    status: TaskStatus
    diarization_task_id: str = Field(..., description="원본 화자 분리 작업 ID")
    segments: list[MinutesSegment] = Field(default_factory=list, description="회의록 세그먼트 목록")
    speakers: list[SpeakerStats] = Field(default_factory=list, description="화자별 통계")
    total_duration: float = Field(..., description="총 대화 시간 (초)")
    total_speakers: int = Field(..., description="총 화자 수")
    # markdown: output_format=markdown 요청 시 생성 (REQ-MIN-003)
    markdown: str | None = Field(default=None, description="마크다운 형식 회의록")
    error_message: str | None = Field(default=None, description="실패 시 오류 메시지")


class MinutesStatusResponse(BaseModel):
    """GET /api/v1/minutes/{task_id}/status 응답"""

    task_id: str = Field(..., description="회의록 작업 ID")
    status: TaskStatus
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="진행률 (0.0~1.0)")
    message: str | None = Field(default=None, description="상태 메시지")
    error_message: str | None = Field(default=None, description="실패 시 오류 메시지")
