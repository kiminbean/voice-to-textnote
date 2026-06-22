"""
화자별 통계 서비스
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import NotFoundError
from backend.db.models import TaskResult
from backend.db.speaker_models import SpeakerProfile
from backend.schemas.speaker_statistics import (
    ActivityHour,
    ParticipationMeeting,
    SpeakerMeeting,
    SpeakerStatistics,
    SpeakerStatisticsResponse,
)


class SpeakerStatisticsService:
    """화자별 통계 서비스"""

    async def _get_speaker(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeakerProfile:
        result = await session.execute(
            select(SpeakerProfile).where(
                SpeakerProfile.id == speaker_id,
                SpeakerProfile.user_id == user_id,
            )
        )
        speaker = result.scalar_one_or_none()
        if not speaker:
            raise NotFoundError(message="화자 프로필을 찾을 수 없습니다.")
        return speaker

    async def _load_segmented_tasks(
        self,
        session: AsyncSession,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[TaskResult]:
        query = select(TaskResult).where(
            TaskResult.task_type.in_(["minutes", "summary"]),
            func.json_extract(TaskResult.result_data, "$.segments").isnot(None),
            func.json_extract(TaskResult.result_data, "$.segments").cast(String) != "[]",
        )
        if date_from:
            query = query.where(TaskResult.created_at >= date_from)
        if date_to:
            query = query.where(TaskResult.created_at <= date_to)

        result = await session.execute(query.order_by(TaskResult.created_at.desc()))
        return list(result.scalars().all())

    def _segments_for_task(self, task: TaskResult) -> list[dict[str, Any]]:
        result_data = task.result_data if isinstance(task.result_data, dict) else {}
        segments = result_data.get("segments", [])
        if not isinstance(segments, list):
            return []
        return [segment for segment in segments if isinstance(segment, dict)]

    def _speaker_segments(
        self,
        segments: list[dict[str, Any]],
        speaker_label: str,
    ) -> list[dict[str, Any]]:
        return [segment for segment in segments if segment.get("speaker") == speaker_label]

    def _segment_duration(self, segment: dict[str, Any]) -> int:
        start = segment.get("start", 0) or 0
        end = segment.get("end", 0) or 0
        try:
            return max(0, int(round(float(end) - float(start))))
        except (TypeError, ValueError):
            return 0

    def _speaker_duration(self, segments: list[dict[str, Any]]) -> int:
        return sum(self._segment_duration(segment) for segment in segments)

    def _meeting_title(self, task: TaskResult) -> str | None:
        result_data = task.result_data if isinstance(task.result_data, dict) else {}
        input_metadata = task.input_metadata if isinstance(task.input_metadata, dict) else {}
        title = result_data.get("title") or result_data.get("task_name") or input_metadata.get("title")
        return str(title) if title is not None else None

    def _meeting_duration(self, task: TaskResult, segments: list[dict[str, Any]]) -> int:
        result_data = task.result_data if isinstance(task.result_data, dict) else {}
        input_metadata = task.input_metadata if isinstance(task.input_metadata, dict) else {}
        explicit_duration = (
            result_data.get("duration_seconds")
            or result_data.get("duration")
            or input_metadata.get("duration_seconds")
            or input_metadata.get("duration")
        )
        if explicit_duration is not None:
            try:
                return max(0, int(round(float(explicit_duration))))
            except (TypeError, ValueError):
                pass

        ends = []
        for segment in segments:
            try:
                ends.append(int(round(float(segment.get("end", 0) or 0))))
            except (TypeError, ValueError):
                continue
        return max(ends, default=0)

    async def get_speaker_meetings(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SpeakerMeeting], int]:
        """화자가 참여한 회의 목록 조회."""
        speaker = await self._get_speaker(session, speaker_id, user_id)
        tasks = await self._load_segmented_tasks(session, date_from, date_to)

        meetings = []
        for task in tasks:
            segments = self._segments_for_task(task)
            speaker_segments = self._speaker_segments(segments, speaker.speaker_label)
            if not speaker_segments:
                continue

            meetings.append(
                SpeakerMeeting(
                    task_id=task.task_id,
                    title=self._meeting_title(task),
                    created_at=task.created_at,
                    duration_seconds=self._meeting_duration(task, segments),
                    speaker_segments_count=len(speaker_segments),
                    speaker_duration_seconds=self._speaker_duration(speaker_segments),
                )
            )

        return meetings[offset : offset + limit], len(meetings)

    async def get_speaker_statistics(
        self,
        session,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SpeakerStatisticsResponse:
        """화자별 회의 통계 계산."""
        speaker = await self._get_speaker(session, speaker_id, user_id)
        tasks = await self._load_segmented_tasks(session, date_from, date_to)

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
        meeting_speaker_data = {}  # meeting별 화자 데이터

        for task in tasks:
            segments = self._segments_for_task(task)
            speaker_segments = self._speaker_segments(segments, speaker.speaker_label)
            if not speaker_segments:
                continue

            meeting_duration = self._meeting_duration(task, segments)
            speaker_duration = self._speaker_duration(speaker_segments)

            total_meetings_duration += meeting_duration
            total_speaker_duration += speaker_duration
            speaker_segments_count += len(speaker_segments)

            meeting_speaker_data[task.task_id] = {
                "meeting_duration": meeting_duration,
                "speaker_duration": speaker_duration,
            }

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
                key=lambda x: x[1]["speaker_duration"],
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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        """화자별 활동 시간대 분석."""
        speaker = await self._get_speaker(session, speaker_id, user_id)

        # 시간대별 활동 데이터 집계
        hourly_activity = {hour: {"segment_count": 0, "duration_seconds": 0} for hour in range(24)}

        tasks = await self._load_segmented_tasks(session, date_from, date_to)

        total_activity_seconds = 0

        for task in tasks:
            segments = self._segments_for_task(task)
            speaker_segments = self._speaker_segments(segments, speaker.speaker_label)
            for segment in speaker_segments:
                try:
                    start_time = float(segment.get("start", 0) or 0)
                except (TypeError, ValueError):
                    start_time = 0
                hour = int(start_time // 3600) % 24

                duration = self._segment_duration(segment)
                hourly_activity[hour]["segment_count"] += 1
                hourly_activity[hour]["duration_seconds"] += duration
                total_activity_seconds += duration

        # ActivityHour 객체로 변환
        activity_hours = []
        for hour, data in hourly_activity.items():
            if data["duration_seconds"] > 0:
                activity_percentage = (
                    data["duration_seconds"] / total_activity_seconds * 100
                ) if total_activity_seconds > 0 else 0
                activity_hours.append(
                    ActivityHour(
                        hour=hour,
                        segment_count=data["segment_count"],
                        duration_seconds=data["duration_seconds"],
                        activity_percentage=round(activity_percentage, 2),
                    )
                )

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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        """화자별 참여도 분석."""
        speaker = await self._get_speaker(session, speaker_id, user_id)
        tasks = await self._load_segmented_tasks(session, date_from, date_to)

        meetings = []
        total_participation_percentage = 0.0
        participations = []

        for task in tasks:
            segments = self._segments_for_task(task)
            speaker_segments = self._speaker_segments(segments, speaker.speaker_label)
            if not speaker_segments:
                continue

            meeting_duration = self._meeting_duration(task, segments)
            speaker_duration = self._speaker_duration(speaker_segments)
            participation_percentage = (
                speaker_duration / meeting_duration * 100
            ) if meeting_duration > 0 else 0.0

            participations.append(participation_percentage)
            total_participation_percentage += participation_percentage

            meeting = ParticipationMeeting(
                task_id=task.task_id,
                title=self._meeting_title(task),
                meeting_duration_seconds=meeting_duration,
                speaker_duration_seconds=speaker_duration,
                participation_percentage=round(participation_percentage, 2),
                segment_count=len(speaker_segments),
                is_most_participated=False,
            )
            meetings.append(meeting)
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
