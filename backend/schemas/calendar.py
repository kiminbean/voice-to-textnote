"""
캘린더 통합 API 스키마
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CalendarEvent(BaseModel):
    """캘린더 이벤트 모델"""
    title: str = Field(..., description="이벤트 제목")
    description: str = Field(..., description="이벤트 설명")
    start_datetime: datetime = Field(..., description="시작 일시")
    end_datetime: datetime = Field(..., description="종료 일시")
    location: str = Field(default="온라인 미팅", description="장소")
    participants: List[str] = Field(default_factory=list, description="참가자 목록")
    action_items: List[str] = Field(default_factory=list, description="액션 아이템 목록")
    duration_minutes: int = Field(..., ge=1, description="지속 시간 (분)")
    calendar_type: str = Field(default="google", description="캘린더 타입")
    status: str = Field(default="confirmed", description="이벤트 상태")
    created_at: Optional[datetime] = Field(default=None, description="생성 일시")
    updated_at: Optional[datetime] = Field(default=None, description="업데이트 일시")


class CalendarEventCreate(BaseModel):
    """캘린더 이벤트 생성 요청"""
    title: str = Field(..., description="이벤트 제목")
    description: str = Field(..., description="이벤트 설명")
    start_datetime: datetime = Field(..., description="시작 일시")
    end_datetime: datetime = Field(..., description="종료 일시")
    location: str = Field(default="온라인 미팅", description="장소")
    participants: List[str] = Field(default_factory=list, description="찼가자 목록")
    calendar_type: str = Field(default="google", description="캘린더 타입")


class CalendarEventResponse(BaseModel):
    """캘린더 이벤트 응답"""
    success: bool = Field(..., description="요청 성공 여부")
    message: str = Field(..., description="응답 메시지")
    event: CalendarEvent = Field(..., description="캘린더 이벤트")