"""
SPEC-ENHANCED-STATS-001: 고급 통계 대시보드 서비스

시계열 분석, 화자 참여도 패턴, 키워드 빈도 추이, 회의 효율성 지표 계산
"""

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TaskResult
from backend.schemas.enhanced_statistics import (
    EfficiencyMetrics,
    EnhancedStatisticsResponse,
    KeywordTrend,
    MeetingSummary,
    OverviewResponse,
    SpeakerParticipationPattern,
    TimeSeriesDataPoint,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def _fetch_minutes_result(
    redis_client: aioredis.Redis,
    db: AsyncSession,
    task_id: str,
) -> dict[str, Any] | None:
    """Redis 우선, DB 폴백으로 minutes 결과를 조회.

    export.py 의 _get_task_result 와 독립된 서비스 레이어 구현 (API 의존 제거).
    """
    redis_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(redis_key)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            # Redis 캐시가 손상되었을 때 DB로 폴백시키기 위해 None을 반환한다.
            logger.warning(
                "회의록 Redis 캐시 JSON 파싱 실패 — DB 폴백",
                task_id=task_id,
                error=str(exc),
            )

    stmt = select(TaskResult).where(
        TaskResult.task_id == task_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
    )
    result = await db.execute(stmt)
    record = result.scalars().first()
    if record and record.result_data:
        return record.result_data
    return None


class EnhancedStatisticsService:
    """고급 통계 계산기.

    의존성:
        - redis_client: Redis 캐시 조회용
        - db: DB 폴백용 (Redis 미스 시)
    """

    async def get_enhanced_statistics(
        self,
        task_id: str,
        time_range: str,
        top_n_keywords: int,
        include_speaker_analysis: bool,
        include_efficiency_metrics: bool,
        db: AsyncSession,
        redis_client: aioredis.Redis,
    ) -> EnhancedStatisticsResponse:
        """고급 통계 정보를 계산하여 반환.

        Args:
            task_id: 분석할 회의록 task ID
            time_range: 분석 시간 범위 (1d, 7d, 30d, 90d)
            top_n_keywords: 상위 키워드 수
            include_speaker_analysis: 화자별 분석 포함 여부
            include_efficiency_metrics: 효율성 지표 포함 여부
            db: 데이터베이스 세션
            redis_client: Redis 클라이언트

        Returns:
            EnhancedStatisticsResponse: 고급 통계 응답
        """
        # 1) minutes 결과 조회 (Redis 우선, DB 폴백)
        data = await _fetch_minutes_result(redis_client, db, task_id)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"회의록 데이터를 찾을 수 없습니다: task_id={task_id}",
            )

        segments = data.get("segments") or []
        if not isinstance(segments, list) or not segments:
            # 세그먼트 없음 — 빈 통계 반환
            return EnhancedStatisticsResponse(
                task_id=task_id,
                time_range=time_range,
                time_series=[],
                speaker_patterns=[],
                keyword_trends=[],
                efficiency_metrics=None,
                metadata={"warning": "세그먼트 데이터가 없습니다."},
            )

        # 2) 시계열 데이터 생성
        time_series = self._generate_time_series(segments, time_range)

        # 3) 화자별 참여도 패턴 분석
        speaker_patterns = (
            self._analyze_speaker_patterns(segments) if include_speaker_analysis else []
        )

        # 4) 키워드 빈도 추이 분석
        keyword_trends = self._analyze_keyword_trends(segments, top_n_keywords)

        # 5) 효율성 지표 계산
        efficiency_metrics = (
            self._calculate_efficiency_metrics(segments) if include_efficiency_metrics else None
        )

        return EnhancedStatisticsResponse(
            task_id=task_id,
            time_range=time_range,
            time_series=time_series,
            speaker_patterns=speaker_patterns,
            keyword_trends=keyword_trends,
            efficiency_metrics=efficiency_metrics,
            metadata={
                "total_segments": len(segments),
                "analysis_timestamp": datetime.now().isoformat(),
            },
        )

    async def get_project_overview(
        self,
        period: str,
        top_meetings: int,
        db: AsyncSession,
        redis_client: aioredis.Redis,
    ) -> OverviewResponse:
        """프로젝트 전체 통계 개요를 계산하여 반환.

        Args:
            period: 통계 기간 (7d, 30d, 90d, 180d)
            top_meetings: 상위 회의 수
            db: 데이터베이스 세션
            redis_client: Redis 클라이언트

        Returns:
            OverviewResponse: 프로젝트 개요 응답
        """
        # 기간별 날짜 범위 계산
        period_days = self._parse_period(period)
        start_date = datetime.now() - timedelta(days=period_days)

        # 1) 전체 회의 통계 조회
        stmt = select(TaskResult).where(
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed",
            TaskResult.created_at >= start_date,
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        total_meetings = len(records)
        total_duration = 0.0
        all_participants: set[str] = set()
        efficiency_scores: list[float] = []

        # 상위 회의 수집
        meeting_summaries: list[dict[str, Any]] = []

        for record in records:
            segments = record.result_data.get("segments", []) if record.result_data else []
            duration = self._calculate_total_duration(segments)
            total_duration += duration

            # 참가자 추출
            for seg in segments:
                if isinstance(seg, dict) and seg.get("speaker"):
                    all_participants.add(seg["speaker"])

            # 효율성 점수 계산
            efficiency = self._calculate_efficiency_score(segments)
            efficiency_scores.append(efficiency)

            # 상위 회의 후보
            meeting_summaries.append(
                {
                    "task_id": record.task_id,
                    "duration": duration,
                    "efficiency": efficiency,
                    "created_at": record.created_at,
                    "participant_count": len(
                        {
                            s.get("speaker")
                            for s in segments
                            if isinstance(s, dict) and s.get("speaker")
                        }
                    ),
                }
            )

        # 2) 상위 회의 정렬 및 제한
        meeting_summaries.sort(key=lambda x: (x["efficiency"], x["duration"]), reverse=True)
        top_meeting_data = meeting_summaries[:top_meetings]

        top_meetings_list = [
            MeetingSummary(
                task_id=m["task_id"],
                title=None,  # 제목 필드가 없으면 None
                date=m["created_at"],
                duration_seconds=m["duration"],
                participant_count=m["participant_count"],
                efficiency_score=round(m["efficiency"], 3),
            )
            for m in top_meeting_data
        ]

        # 3) 평균 효율성 점수
        avg_efficiency = (
            sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0.0
        )

        # 4) 활발한 화자 목록 (발화 시간 기준 상위 10)
        speaker_durations: dict[str, float] = {}
        for record in records:
            segments = record.result_data.get("segments", []) if record.result_data else []
            for seg in segments:
                if isinstance(seg, dict):
                    speaker = seg.get("speaker", "UNKNOWN")
                    start = float(seg.get("start", 0) or 0)
                    end = float(seg.get("end", 0) or 0)
                    speaker_durations[speaker] = speaker_durations.get(speaker, 0.0) + max(
                        0.0, end - start
                    )

        active_speakers = [
            speaker for speaker, _ in sorted(speaker_durations.items(), key=lambda x: -x[1])[:10]
        ]

        # 5) 트렌딩 키워드 (전체 세그먼트 집계)
        all_segments: list[dict[str, Any]] = []
        for record in records:
            segments = record.result_data.get("segments", []) if record.result_data else []
            all_segments.extend(segments)

        trending_keywords = self._analyze_keyword_trends(all_segments, 10)

        return OverviewResponse(
            period=period,
            total_meetings=total_meetings,
            total_duration_seconds=round(total_duration, 3),
            total_participants=len(all_participants),
            average_efficiency_score=round(avg_efficiency, 3),
            top_meetings=top_meetings_list,
            active_speakers=active_speakers,
            trending_keywords=trending_keywords,
            metadata={
                "start_date": start_date.isoformat(),
                "end_date": datetime.now().isoformat(),
                "analysis_timestamp": datetime.now().isoformat(),
            },
        )

    def _generate_time_series(
        self, segments: list[dict[str, Any]], time_range: str
    ) -> list[TimeSeriesDataPoint]:
        """시계열 데이터 생성.

        Args:
            segments: 세그먼트 리스트
            time_range: 시간 범위 (1d, 7d, 30d, 90d)

        Returns:
            시계열 데이터 포인트 리스트
        """
        # 시간 범위에 따라 버킷 크기 결정
        period_hours = self._parse_period(time_range) * 24
        if period_hours <= 24:
            bucket_hours = 1  # 1일 이하: 1시간 단위
        elif period_hours <= 168:  # 7일
            bucket_hours = 6  # 7일: 6시간 단위
        else:
            bucket_hours = 24  # 30일 이상: 1일 단위

        # 버킷별 발화량 집계
        buckets: dict[datetime, float] = {}

        for seg in segments:
            if not isinstance(seg, dict):
                continue

            try:
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", 0) or 0)
            except (TypeError, ValueError):
                continue

            duration = max(0.0, end - start)

            # 버킷 시간 계산
            bucket_time = datetime.fromtimestamp(start).replace(minute=0, second=0, microsecond=0)
            hour_offset = int(start / 3600) % bucket_hours
            bucket_time = bucket_time - timedelta(hours=hour_offset)

            buckets[bucket_time] = buckets.get(bucket_time, 0.0) + duration

        # TimeSeriesDataPoint 변환
        time_series = [
            TimeSeriesDataPoint(
                timestamp=ts,
                value=round(duration, 3),
                label=f"{bucket_hours}h" if bucket_hours < 24 else "1d",
            )
            for ts, duration in sorted(buckets.items())
        ]

        return time_series

    def _analyze_speaker_patterns(
        self, segments: list[dict[str, Any]]
    ) -> list[SpeakerParticipationPattern]:
        """화자별 참여도 패턴 분석.

        Args:
            segments: 세그먼트 리스트

        Returns:
            화자별 참여도 패턴 리스트
        """
        speaker_data: dict[str, dict[str, Any]] = {}

        for seg in segments:
            if not isinstance(seg, dict):
                continue

            speaker = str(seg.get("speaker") or "UNKNOWN")

            try:
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", 0) or 0)
            except (TypeError, ValueError):
                continue

            duration = max(0.0, end - start)
            hour = datetime.fromtimestamp(start).strftime("%H:00")

            if speaker not in speaker_data:
                speaker_data[speaker] = {
                    "total_time": 0.0,
                    "segment_count": 0,
                    "durations": [],
                    "hours": {},
                }

            speaker_data[speaker]["total_time"] += duration
            speaker_data[speaker]["segment_count"] += 1
            speaker_data[speaker]["durations"].append(duration)
            speaker_data[speaker]["hours"][hour] = speaker_data[speaker]["hours"].get(hour, 0) + 1

        # 전체 발화 시간 계산
        total_time = sum(data["total_time"] for data in speaker_data.values())

        patterns = []
        for speaker, data in speaker_data.items():
            # 참여율
            participation_rate = data["total_time"] / total_time if total_time > 0 else 0.0

            # 평균 발화 구간 길이
            avg_segment_length = (
                sum(data["durations"]) / len(data["durations"]) if data["durations"] else 0.0
            )

            # 끼어든 횟수 (발화 전환 수 추정)
            intervention_count = data["segment_count"]

            # 가장 활발한 시간대
            most_active_hour = (
                max(data["hours"].items(), key=lambda x: x[1])[0][0] if data["hours"] else "N/A"
            )

            patterns.append(
                SpeakerParticipationPattern(
                    speaker=speaker,
                    total_speaking_time=round(data["total_time"], 3),
                    participation_rate=round(participation_rate, 4),
                    average_segment_length=round(avg_segment_length, 3),
                    intervention_count=intervention_count,
                    most_active_hour=most_active_hour,
                )
            )

        # 발화 시간 기준 정렬
        patterns.sort(key=lambda x: -x.total_speaking_time)

        return patterns

    def _analyze_keyword_trends(
        self, segments: list[dict[str, Any]], top_n: int
    ) -> list[KeywordTrend]:
        """키워드 빈도 추이 분석.

        Args:
            segments: 세그먼트 리스트
            top_n: 상위 키워드 수

        Returns:
            키워드 빈도 추이 리스트
        """
        # 키워드 추출
        keywords = []
        keyword_appearances: dict[str, list[datetime]] = {}

        for seg in segments:
            if not isinstance(seg, dict):
                continue

            text = str(seg.get("text") or "")
            try:
                start = float(seg.get("start", 0) or 0)
            except (TypeError, ValueError):
                continue

            seg_time = datetime.fromtimestamp(start)

            # 간단한 토큰화 (공백/문장부호 기준)
            tokens = text.split()
            for token in tokens:
                # 불용어 제거
                if len(token) < 2:
                    continue
                token_lower = token.lower()
                keywords.append(token_lower)

                if token_lower not in keyword_appearances:
                    keyword_appearances[token_lower] = []
                keyword_appearances[token_lower].append(seg_time)

        # 빈도 집계
        counter = Counter(keywords)

        trends = []
        for keyword, count in counter.most_common(top_n):
            appearances = keyword_appearances.get(keyword, [])
            first_appearance = min(appearances) if appearances else None
            last_appearance = max(appearances) if appearances else None

            # 추세 방향 (단순히 등장 시간 기준)
            trend_direction = "stable"
            frequency_change = float(count)
            if first_appearance is not None and last_appearance is not None:
                time_diff = (last_appearance - first_appearance).total_seconds()
                if time_diff > 0:
                    frequency_change = count / (time_diff / 3600)  # 시간당 빈도
                    if frequency_change > 1.0:
                        trend_direction = "up"
                    elif frequency_change < 0.5:  # pragma: no cover
                        trend_direction = "down"
                else:
                    frequency_change = float(count)  # pragma: no cover

            trends.append(
                KeywordTrend(
                    keyword=keyword,
                    total_count=count,
                    trend_direction=trend_direction,
                    frequency_change=round(frequency_change, 3),
                    first_appearance=first_appearance,
                    last_appearance=last_appearance,
                )
            )

        return trends

    def _calculate_efficiency_metrics(self, segments: list[dict[str, Any]]) -> EfficiencyMetrics:
        """회의 효율성 지표 계산.

        Args:
            segments: 세그먼트 리스트

        Returns:
            효율성 지표
        """
        if not segments:
            return EfficiencyMetrics(
                total_duration_seconds=0.0,
                effective_duration_seconds=0.0,
                silence_ratio=0.0,
                speaking_turn_count=0,
                average_turn_length=0.0,
                participation_balance=0.0,
            )

        total_duration = 0.0
        effective_duration = 0.0
        speaking_turn_count = len(segments)
        turn_lengths = []
        speaker_durations: dict[str, float] = {}

        for seg in segments:
            if not isinstance(seg, dict):
                continue

            try:
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", 0) or 0)
            except (TypeError, ValueError):
                continue

            duration = max(0.0, end - start)
            speaker = str(seg.get("speaker") or "UNKNOWN")

            total_duration = max(total_duration, end)  # 전체 회의 시간
            effective_duration += duration
            turn_lengths.append(duration)
            speaker_durations[speaker] = speaker_durations.get(speaker, 0.0) + duration

        # 침묵 비율
        silence_ratio = (
            (total_duration - effective_duration) / total_duration if total_duration > 0 else 0.0
        )

        # 평균 발화 전환 길이
        avg_turn_length = sum(turn_lengths) / len(turn_lengths) if turn_lengths else 0.0

        # 참여 균형도 (화자별 발화 시간의 표준편차 기반)
        if speaker_durations:
            times = list(speaker_durations.values())
            mean_time = sum(times) / len(times)
            variance = sum((t - mean_time) ** 2 for t in times) / len(times)
            std_dev = variance**0.5
            # 표준편차가 작을수록 균형적 (1에서 표준편비를 뺌)
            participation_balance = max(0.0, 1.0 - (std_dev / mean_time if mean_time > 0 else 0.0))
        else:
            participation_balance = 0.0  # pragma: no cover

        return EfficiencyMetrics(
            total_duration_seconds=round(total_duration, 3),
            effective_duration_seconds=round(effective_duration, 3),
            silence_ratio=round(silence_ratio, 4),
            speaking_turn_count=speaking_turn_count,
            average_turn_length=round(avg_turn_length, 3),
            participation_balance=round(participation_balance, 4),
        )

    def _calculate_efficiency_score(self, segments: list[dict[str, Any]]) -> float:
        """효율성 점수 계산 (0~1).

        Args:
            segments: 세그먼트 리스트

        Returns:
            효율성 점수
        """
        metrics = self._calculate_efficiency_metrics(segments)

        # 가중 평균으로 계산
        # - 침묵 비율이 낮을수록 좋음 (0.3 이상이면 패널티)
        silence_penalty = max(0.0, (metrics.silence_ratio - 0.3) / 0.7)

        # - 참여 균형도가 높을수록 좋음
        balance_bonus = metrics.participation_balance

        # - 평균 발화 전환 길이가 30~120초 사이가 좋음
        turn_bonus = 1.0
        if metrics.average_turn_length < 30:
            turn_bonus = metrics.average_turn_length / 30
        elif metrics.average_turn_length > 120:
            turn_bonus = max(0.0, 1.0 - (metrics.average_turn_length - 120) / 120)

        # 종합 점수
        efficiency = max(0.0, min(1.0, (balance_bonus + turn_bonus) / 2 - silence_penalty))

        return efficiency

    def _calculate_total_duration(self, segments: list[dict[str, Any]]) -> float:
        """총 발화 시간 계산.

        Args:
            segments: 세그먼트 리스트

        Returns:
            총 발화 시간 (초)
        """
        if not segments:
            return 0.0

        max_end = 0.0
        for seg in segments:
            if isinstance(seg, dict):
                try:
                    end = float(seg.get("end", 0) or 0)
                    max_end = max(max_end, end)
                except (TypeError, ValueError):
                    continue

        return max_end

    def _parse_period(self, period: str) -> int:
        """기간 문자열을 일수로 변환.

        Args:
            period: 기간 문자열 (7d, 30d, 90d, 180d)

        Returns:
            일수
        """
        try:
            return int(period.rstrip("d"))
        except (ValueError, AttributeError):
            return 30  # 기본값 30일
