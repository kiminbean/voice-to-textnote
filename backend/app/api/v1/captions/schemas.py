"""
자막 API 관련 Pydantic 스키마
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CaptionFormat(str, Enum):
    """자막 형식"""
    VTT = "vtt"
    SRT = "srt"
    JSON = "json"


class CaptionStatus(str, Enum):
    """자막 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class CaptionSegment(BaseModel):
    """자막 세그먼트"""
    index: int = Field(..., description="세그먼트 인덱스")
    text: str = Field(..., description="자막 텍스트")
    start_time: datetime = Field(..., description="시작 시간")
    end_time: datetime = Field(..., description="종료 시간")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도")
    speaker_id: str | None = Field(None, description="화자 ID")


class CaptionSession(BaseModel):
    """자막 세션"""
    session_id: str = Field(..., description="세션 ID")
    meeting_id: str = Field(..., description="회의 ID")
    user_id: str = Field(..., description="사용자 ID")
    status: CaptionStatus = Field(..., description="상태")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime | None = Field(None, description="업데이트 시간")
    segments: list[CaptionSegment] = Field(default_factory=list, description="자막 세그먼트")


class CaptionCreateRequest(BaseModel):
    """자막 생성 요청"""
    meeting_id: str = Field(..., description="회의 ID")
    audio_url: str | None = Field(None, description="오디오 파일 URL")
    language: str = Field(default="ko", description="언어 코드 (ko, en, ja)")
    format: CaptionFormat = Field(default=CaptionFormat.VTT, description="출력 형식")


class CaptionSessionResponse(BaseModel):
    """자막 세션 응답"""
    session_id: str = Field(..., description="세션 ID")
    meeting_id: str = Field(..., description="회의 ID")
    user_id: str = Field(..., description="사용자 ID")
    status: CaptionStatus = Field(..., description="상태")
    created_at: datetime = Field(..., description="생성 시간")
    segment_count: int = Field(..., description="세그먼트 수")


class CaptionResponse(BaseModel):
    """자막 응답"""
    task_id: str = Field(..., description="작업 ID")
    status: CaptionStatus = Field(..., description="상태")
    message: str = Field(..., description="메시지")


class WebVTTResponse(BaseModel):
    """WebVTT 응답"""
    content: str = Field(..., description="VTT 콘텐츠")
    filename: str = Field(..., description="파일 이름")
