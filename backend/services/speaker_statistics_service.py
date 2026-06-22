"""
화자별 통계 서비스
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import and_

from backend.app.dependencies import get_db_session
from backend.db.models import TaskResult
from backend.db.speaker_models import SpeakerProfile
from backend.exceptions import VoiceNoteError
from backend.schemas.speaker_statistics import (
    ActivityHour,
    ParticipationMeeting,
    SpeakerMeeting,
    SpeakerStatistics,
    SpeakerStatisticsResponse,
)


class SpeakerStatisticsService:
    """화자별 통계 서비스"""
    
    async def get_speaker_meetings(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SpeakerMeeting], int]:
        """화자가 참여한 회의 목록 조회."""
        # 화자 프로필 존재 확인
        speaker_result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = speaker_result.scalar_one_or_none()
        if not speaker:
            raise VoiceNoteError("화자 프로필을 찾을 수 없습니다.")
        
        # 해당 화자가 참여한 회의 조회
        TaskResultAlias = aliased(TaskResult)
        
        query = select(TaskResult).where(
            TaskResult.task_type.in_(["minutes", "summary"]),
            # 해당 화자의 segments가 있는 회의만 선택
            func.json_extract(TaskResult.result_data, '$.segments').isnot(None),
            func.json_extract(TaskResult.result_data, '$.segments').cast('TEXT') != '[]',
        )
        
        # 날짜 필터
        if date_from:
            query = query.where(TaskResult.created_at >= date_from)
        if date_to:
            query = query.where(TaskResult.created_at <= date_to)
        
        # 총 개수 조회
        total_query = query.with_only_columns(func.count(TaskResult.id))
        total = await session.scalar(total_query)
        
        # 상세 조회 - segments에서 해당 화자 데이터 추출
        meetings = []
        result = await session.execute(
            query.order_by(TaskResult.created_at.desc()).offset(offset).limit(limit)
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            try:
                segments = task.result_data.get("segments", [])
                speaker_segments = [
                    s for s in segments if s.get("speaker") == speaker.speaker_label
                ]
                
                if speaker_segments:
                    meeting = SpeakerMeeting(
                        task_id=task.task_id,
                        title=task.task_name,
                        created_at=task.created_at,
                        duration_seconds=task.duration_seconds,
                        speaker_segments_count=len(speaker_segments),
                        speaker_duration_seconds=sum(s.get("end", 0) - s.get("start", 0) for s in speaker_segments),
                    )
                    meetings.append(meeting)
            except Exception as e:
                # 데이터 파싱 오류는 건너뜀
                continue
        
        return meetings, total
    
    async def get_speaker_statistics(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> SpeakerStatisticsResponse:
        """화자별 회의 통계 계산."""
        # 화자 프로필 존재 확인
        speaker_result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = speaker_result.scalar_one_or_none()
        if not speaker:
            raise VoiceNoteError("화자 프로필을 찾을 수 없습니다.")
        
        # 해당 화자가 참여한 회의 조회 및 집계
        TaskResultAlias = aliased(TaskResult)
        
        query = select(TaskResult).where(
            TaskResult.task_type.in_(["minutes", "summary"]),
            func.json_extract(TaskResult.result_data, '$.segments').isnot(None),
            func.json_extract(TaskResult.result_data, '$.segments').cast('TEXT') != '[]',
        )
        
        # 날짜 필터
        if date_from:
            query = query.where(TaskResult.created_at >= date_from)
        if date_to:
            query = query.where(TaskResult.created_at <= date_to)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        if not tasks:
            return SpeakerStatisticsResponse(
                speaker_id=speaker_id,
                statistics_period={
                    "date_from": date_from,
                    "date_to": date_to,
                },
                statistics=SpeakerStatistics(
                    total_meetings=0,
                    total_speaker_duration_seconds=0,
                    total_meetings_duration_seconds=0,
                    average_speaker_percentage=0.0,
                    speaker_segments_count=0,
                    average_segment_duration_seconds=0.0,
                    key_words=[],
                ),
            )
        
        total_speaker_duration = 0
        total_meetings_duration = 0
        speaker_segments_count = 0
        speaker_durations = []
        meeting_speaker_data = {}  # meeting별 화자 데이터
        
        for task in tasks:
            try:
                segments = task.result_data.get("segments", [])
                speaker_segments = [
                    s for s in segments if s.get("speaker") == speaker.speaker_label
                ]
                
                if speaker_segments:
                    meeting_duration = task.duration_seconds or 0
                    speaker_duration = sum(s.get("end", 0) - s.get("start", 0) for s in speaker_segments)
                    
                    total_meetings_duration += meeting_duration
                    total_speaker_duration += speaker_duration
                    speaker_segments_count += len(speaker_segments)
                    speaker_durations.append(speaker_duration)
                    
                    meeting_speaker_data[task.task_id] = {
                        "meeting_duration": meeting_duration,
                        "speaker_duration": speaker_duration,
                    }
                    
            except Exception:
                continue
        
        # 통계 계산
        total_meetings = len(meeting_speaker_data)
        average_speaker_percentage = (
            (total_speaker_duration / total_meetings_duration * 100) if total_meetings_duration > 0 else 0
        )
        
        avg_segment_duration = (
            total_speaker_duration / speaker_segments_count if speaker_segments_count > 0 else 0
        )
        
        # 가장 활발했던 회의 찾기
        most_active_meeting = None
        if meeting_speaker_data:
            most_active_meeting = max(
                meeting_speaker_data.items(),
                key=lambda x: x[1]["speaker_duration"]
            )[0]
        
        return SpeakerStatisticsResponse(
            speaker_id=speaker_id,
            statistics_period={
                "date_from": date_from,
                "date_to": date_to,
            },
            statistics=SpeakerStatistics(
                total_meetings=total_meetings,
                total_speaker_duration_seconds=total_speaker_duration,
                total_meetings_duration_seconds=total_meetings_duration,
                average_speaker_percentage=round(average_speaker_percentage, 2),
                speaker_segments_count=speaker_segments_count,
                average_segment_duration_seconds=round(avg_segment_duration, 2),
                most_active_meeting=most_active_meeting,
                key_words=[],  # 키워드 추출은 별도 서비스에서 구현
            ),
        )
    
    async def get_activity_timeline(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        """화자별 활동 시간대 분석."""
        speaker_result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = speaker_result.scalar_one_or_none()
        if not speaker:
            raise VoiceNoteError("화자 프로필을 찾을 수 없습니다.")
        
        # 시간대별 활동 데이터 집계
        hourly_activity = {hour: {"segment_count": 0, "duration_seconds": 0} for hour in range(24)}
        
        query = select(TaskResult).where(
            TaskResult.task_type.in_(["minutes", "summary"]),
            func.json_extract(TaskResult.result_data, '$.segments').isnot(None),
        )
        
        if date_from:
            query = query.where(TaskResult.created_at >= date_from)
        if date_to:
            query = query.where(TaskResult.created_at <= date_to)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        total_activity_seconds = 0
        
        for task in tasks:
            try:
                segments = task.result_data.get("segments", [])
                speaker_segments = [
                    s for s in segments if s.get("speaker") == speaker.speaker_label
                ]
                
                for segment in speaker_segments:
                    start_time = segment.get("start", 0)
                    hour = int(start_time // 3600) % 24  # 0-23 시간
                    
                    duration = segment.get("end", 0) - segment.get("start", 0)
                    hourly_activity[hour]["segment_count"] += 1
                    hourly_activity[hour]["duration_seconds"] += duration
                    total_activity_seconds += duration
                    
            except Exception:
                continue
        
        # ActivityHour 객체로 변환
        activity_hours = []
        for hour, data in hourly_activity.items():
            if data["duration_seconds"] > 0:
                activity_percentage = (data["duration_seconds"] / total_activity_seconds * 100) if total_activity_seconds > 0 else 0
                activity_hours.append(ActivityHour(
                    hour=hour,
                    segment_count=data["segment_count"],
                    duration_seconds=data["duration_seconds"],
                    activity_percentage=round(activity_percentage, 2),
                ))
        
        # 가장 활발한 시간대 찾기
        peak_hours = []
        if activity_hours:
            max_activity = max(h.activity_percentage for h in activity_hours)
            peak_hours = [h.hour for h in activity_hours if h.activity_percentage == max_activity]
        
        return {
            "speaker_id": speaker_id,
            "period": {"date_from": date_from, "date_to": date_to},
            "hourly_activity": activity_hours,
            "peak_hours": peak_hours,
            "total_activity_seconds": total_activity_seconds,
        }
    
    async def get_participation_analysis(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        """화자별 참여도 분석."""
        speaker_result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = speaker_result.scalar_one_or_none()
        if not speaker:
            raise VoiceNoteError("화자 프로필을 찾을 수 없습니다.")
        
        query = select(TaskResult).where(
            TaskResult.task_type.in_(["minutes", "summary"]),
            func.json_extract(TaskResult.result_data, '$.segments').isnot(None),
        )
        
        if date_from:
            query = query.where(TaskResult.created_at >= date_from)
        if date_to:
            query = query.where(TaskResult.created_at <= date_to)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        meetings = []
        total_participation_percentage = 0
        participations = []
        
        for task in tasks:
            try:
                segments = task.result_data.get("segments", [])
                speaker_segments = [
                    s for s in segments if s.get("speaker") == speaker.speaker_label
                ]
                
                if speaker_segments:
                    meeting_duration = task.duration_seconds or 0
                    speaker_duration = sum(s.get("end", 0) - s.get("start", 0) for s in speaker_segments)
                    participation_percentage = (speaker_duration / meeting_duration * 100) if meeting_duration > 0 else 0
                    
                    participations.append(participation_percentage)
                    total_participation_percentage += participation_percentage
                    
                    meeting = ParticipationMeeting(
                        task_id=task.task_id,
                        title=task.task_name,
                        meeting_duration_seconds=meeting_duration,
                        speaker_duration_seconds=speaker_duration,
                        participation_percentage=round(participation_percentage, 2),
                        segment_count=len(speaker_segments),
                        is_most_participated=False,  # 나중에 설정
                    )
                    meetings.append(meeting)
                    
            except Exception:
                continue
        
        # 평균 참여도 계산
        average_participation = (
            total_participation_percentage / len(participations) if participations else 0
        )
        
        # 가장 높고 낮은 참여도 회의 찾기
        highest_meeting = None
        lowest_meeting = None
        
        if meetings:
            highest = max(meetings, key=lambda m: m.participation_percentage)
            lowest = min(meetings, key=lambda m: m.participation_percentage)
            highest_meeting = highest.task_id
            lowest_meeting = lowest.task_id
            
            # 가장 많이 참여한 회우 표시
            for meeting in meetings:
                meeting.is_most_participated = meeting.task_id == highest_meeting
        
        return {
            "speaker_id": speaker_id,
            "period": {"date_from": date_from, "date_to": date_to},
            "meetings": meetings,
            "average_participation_percentage": round(average_participation, 2),
            "highest_participation_meeting": highest_meeting,
            "lowest_participation_meeting": lowest_meeting,
            "total_meetings_analyzed": len(meetings),
        }