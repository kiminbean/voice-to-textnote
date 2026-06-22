"""
화자별 통계 Schema
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SpeakerMeeting(BaseModel):
    """화자 참여 회의 정보"""
    task_id: str
    title: Optional[str] = None
    created_at: datetime
    duration_seconds: Optional[int] = None
    speaker_segments_count: int
    speaker_duration_seconds: int
    
    class Config:
        from_attributes = True


class SpeakerMeetingsResponse(BaseModel):
    """화자 참여 회의 목록 응답"""
    items: list[SpeakerMeeting]
    total: int
    page: int
    page_size: int
    
    class Config:
        from_attributes = True


class SpeakerStatistics(BaseModel):
    """화자 통계"""
    total_meetings: int
    total_speaker_duration_seconds: int
    total_meetings_duration_seconds: int
    average_speaker_percentage: float  # 화자 평균 참여율 (%)
    speaker_segments_count: int
    average_segment_duration_seconds: float
    most_active_meeting: Optional[str] = None  # 가장 활발했던 회의 task_id
    key_words: list[str] = []
    
    class Config:
        from_attributes = True


class SpeakerStatisticsResponse(BaseModel):
    """화자 통계 응답"""
    speaker_id: uuid.UUID
    statistics_period: dict  # date_from, date_to
    statistics: SpeakerStatistics
    
    class Config:
        from_attributes = True


class ActivityHour(BaseModel):
    """시간대별 활동 정보"""
    hour: int  # 0-23
    segment_count: int
    duration_seconds: int
    activity_percentage: float  # 해당 시간대 전체 활동 중 차지하는 비율


class SpeakerActivityTimelineResponse(BaseModel):
    """활동 시간대 응답"""
    speaker_id: uuid.UUID
    period: dict  # date_from, date_to
    hourly_activity: list[ActivityHour]
    peak_hours: list[int]  # 가장 활발한 시간대 (시간)
    total_activity_seconds: int
    
    class Config:
        from_attributes = True


class ParticipationMeeting(BaseModel):
    """회의별 참여도 정보"""
    task_id: str
    title: Optional[str] = None
    meeting_duration_seconds: int
    speaker_duration_seconds: int
    participation_percentage: float
    segment_count: int
    is_most_participated: bool  # 이 기간 가장 많이 참여한 회의 여부


class SpeakerParticipationResponse(BaseModel):
    """참여도 분석 응답"""
    speaker_id: uuid.UUID
    period: dict  # date_from, date_to
    meetings: list[ParticipationMeeting]
    average_participation_percentage: float
    highest_participation_meeting: Optional[str] = None  # 가장 높은 참여도 회의
    lowest_participation_meeting: Optional[str] = None  # 가장 낮은 참여도 회의
    total_meetings_analyzed: int
    
    class Config:
        from_attributes = True