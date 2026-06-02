"""
고급 통계 서비스 단위 테스트.

SPEC-ENHANCED-STATS-001: 시계열 분석, 화자 참여도 패턴, 키워드 빈도 추이, 회의 효율성 지표 계산
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.services.enhanced_statistics import EnhancedStatisticsService, _fetch_minutes_result


class TestFetchMinutesResult:
    """_fetch_minutes_result 헬퍼 함수 테스트."""

    @pytest.mark.asyncio
    async def test_redis_cache_hit_returns_parsed_data(self):
        """Redis 캐시 히트 시 파싱된 데이터 반환."""
        redis_client = AsyncMock()
        db = AsyncMock()

        test_data = {"segments": [{"text": "test"}], "status": "completed"}
        redis_client.get.return_value = b'{"segments": [{"text": "test"}], "status": "completed"}'

        result = await _fetch_minutes_result(redis_client, db, "task-001")

        assert result == test_data
        redis_client.get.assert_called_once_with("task:min:result:task-001")
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_cache_miss_falls_back_to_db(self):
        """Redis 캐시 미스 시 DB 폴백."""
        redis_client = AsyncMock()
        redis_client.get.return_value = None

        from unittest.mock import MagicMock

        mock_record = MagicMock()
        mock_record.result_data = {"segments": [{"text": "db fallback"}]}

        # MockResult 클래스
        MagicMock()
        MagicMock()

        # first() 메서드가 코루틴이 아닌 MagicMock 객체 반환하도록 설정
        first_result = MagicMock()
        first_result.scalars.return_value = mock_record
        first_result.scalars().first.return_value = mock_record

        db = AsyncMock()
        db.execute.return_value = first_result

        result = await _fetch_minutes_result(redis_client, db, "task-001")

        assert result == {"segments": [{"text": "db fallback"}]}

    @pytest.mark.asyncio
    async def test_redis_json_decode_error_falls_back_to_db(self):
        """Redis JSON 파싱 실패 시 DB 폴백."""
        redis_client = AsyncMock()
        redis_client.get.return_value = b'{invalid json}'

        from unittest.mock import MagicMock

        mock_record = MagicMock()
        mock_record.result_data = {"segments": [{"text": "parsed from db"}]}

        mock_result = MagicMock()
        mock_result.scalars().first.return_value = mock_record

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await _fetch_minutes_result(redis_client, db, "task-001")

        assert result == {"segments": [{"text": "parsed from db"}]}

    @pytest.mark.asyncio
    async def test_both_redis_and_db_miss_return_none(self):
        """Redis와 DB 모두 미스 시 None 반환."""
        redis_client = AsyncMock()
        redis_client.get.return_value = None

        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.scalars().first.return_value = None

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await _fetch_minutes_result(redis_client, db, "task-001")

        assert result is None


class TestEnhancedStatisticsService:
    """EnhancedStatisticsService 테스트."""

    def test_parse_period_converts_valid_periods(self):
        """유효한 기간 문자열을 일수로 변환."""
        service = EnhancedStatisticsService()

        assert service._parse_period("7d") == 7
        assert service._parse_period("30d") == 30
        assert service._parse_period("90d") == 90
        assert service._parse_period("180d") == 180

    def test_parse_period_defaults_to_30_days_on_invalid(self):
        """잘못된 기간 문자열의 경우 기본값 30일 반환."""
        service = EnhancedStatisticsService()

        assert service._parse_period("invalid") == 30
        assert service._parse_period("") == 30
        assert service._parse_period(None) == 30

    def test_calculate_total_duration_with_valid_segments(self):
        """유효한 세그먼트로 총 발화 시간 계산."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0},
            {"start": 30.0, "end": 60.0},
            {"start": 60.0, "end": 120.0},
        ]

        duration = service._calculate_total_duration(segments)

        assert duration == 120.0

    def test_calculate_total_duration_with_empty_segments(self):
        """빈 세그먼트 리스트는 0 반환."""
        service = EnhancedStatisticsService()

        duration = service._calculate_total_duration([])

        assert duration == 0.0

    def test_calculate_total_duration_ignores_invalid_segments(self):
        """잘못된 세그먼트는 무시하고 최대 end 시간 반환."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0},
            {"invalid": "segment"},
            {"start": 60.0, "end": 120.0},
            {"start": "invalid", "end": "invalid"},
        ]

        duration = service._calculate_total_duration(segments)

        assert duration == 120.0

    def test_calculate_efficiency_score_with_balanced_participation(self):
        """균형 잡힌 참여도는 높은 효율 점수."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 45.0, "speaker": "A"},
            {"start": 45.0, "end": 90.0, "speaker": "B"},
            {"start": 90.0, "end": 135.0, "speaker": "C"},
        ]

        score = service._calculate_efficiency_score(segments)

        assert 0.5 <= score <= 1.0

    def test_calculate_efficiency_score_with_imbalanced_participation(self):
        """불균형 참여도는 낮은 효율 점수."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 120.0, "speaker": "A"},
            {"start": 120.0, "end": 125.0, "speaker": "B"},
        ]

        score = service._calculate_efficiency_score(segments)

        assert 0.0 <= score <= 0.8

    def test_calculate_efficiency_score_with_high_silence_ratio(self):
        """높은 침묵 비율은 낮은 효율 점수."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 10.0, "speaker": "A"},
            {"start": 100.0, "end": 110.0, "speaker": "B"},
        ]

        score = service._calculate_efficiency_score(segments)

        # 높은 침묵 비율로 인해 패널티 적용
        assert 0.0 <= score <= 0.6

    @pytest.mark.asyncio
    async def test_get_enhanced_statistics_raises_404_on_missing_data(self):
        """데이터 없을 때 404 예외 발생."""
        service = EnhancedStatisticsService()
        redis_client = AsyncMock()
        redis_client.get.return_value = None

        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_result.scalars().first.return_value = None

        db = AsyncMock()
        db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await service.get_enhanced_statistics(
                task_id="missing-task",
                time_range="7d",
                top_n_keywords=10,
                include_speaker_analysis=True,
                include_efficiency_metrics=True,
                db=db,
                redis_client=redis_client,
            )

        assert exc_info.value.status_code == 404
        assert "회의록 데이터를 찾을 수 없습니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_enhanced_statistics_returns_warning_on_empty_segments(self):
        """빈 세그먼트 시 경고 메시지 반환."""
        service = EnhancedStatisticsService()
        redis_client = AsyncMock()
        redis_client.get.return_value = b'{"segments": []}'
        db = AsyncMock()

        result = await service.get_enhanced_statistics(
            task_id="test-task",
            time_range="7d",
            top_n_keywords=10,
            include_speaker_analysis=True,
            include_efficiency_metrics=True,
            db=db,
            redis_client=redis_client,
        )

        assert result.task_id == "test-task"
        assert result.time_series == []
        assert result.speaker_patterns == []
        assert result.keyword_trends == []
        assert result.efficiency_metrics is None
        assert result.metadata["warning"] == "세그먼트 데이터가 없습니다."

    @pytest.mark.asyncio
    async def test_get_enhanced_statistics_includes_efficiency_metrics_when_requested(self):
        """요청 시 효율성 지표 포함."""
        service = EnhancedStatisticsService()
        redis_client = AsyncMock()
        redis_client.get.return_value = b'{"segments": [{"start": 0.0, "end": 30.0, "speaker": "A", "text": "test segment"}]}'
        db = AsyncMock()

        result = await service.get_enhanced_statistics(
            task_id="test-task",
            time_range="7d",
            top_n_keywords=10,
            include_speaker_analysis=False,
            include_efficiency_metrics=True,
            db=db,
            redis_client=redis_client,
        )

        assert result.efficiency_metrics is not None
        assert result.efficiency_metrics.total_duration_seconds > 0

    @pytest.mark.asyncio
    async def test_get_enhanced_statistics_excludes_efficiency_metrics_when_not_requested(self):
        """요청하지 않을 때 효율성 지표 제외."""
        service = EnhancedStatisticsService()
        redis_client = AsyncMock()
        redis_client.get.return_value = b'{"segments": [{"start": 0.0, "end": 30.0, "speaker": "A", "text": "test segment"}]}'
        db = AsyncMock()

        result = await service.get_enhanced_statistics(
            task_id="test-task",
            time_range="7d",
            top_n_keywords=10,
            include_speaker_analysis=False,
            include_efficiency_metrics=False,
            db=db,
            redis_client=redis_client,
        )

        assert result.efficiency_metrics is None

    @pytest.mark.asyncio
    async def test_get_project_overview_calculates_aggregate_metrics(self):
        """프로젝트 개요 통계 계산."""
        service = EnhancedStatisticsService()

        # Mock DB with multiple meetings
        from unittest.mock import MagicMock

        mock_records = [
            type(
                "MockRecord",
                (),
                {
                    "task_id": f"task-{i:03d}",
                    "task_type": "minutes",
                    "status": "completed",
                    "created_at": datetime.now() - timedelta(days=i),
                    "result_data": {
                        "segments": [
                            {"start": float(i * 30), "end": float(i * 30 + 30), "speaker": f"SPEAKER_{i % 3}"}
                        ]
                    },
                },
            )()
            for i in range(1, 6)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_records
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute.return_value = mock_result

        redis_client = AsyncMock()

        result = await service.get_project_overview(
            period="30d",
            top_meetings=3,
            db=db,
            redis_client=redis_client,
        )

        assert result.period == "30d"
        assert result.total_meetings == 5
        assert result.total_duration_seconds > 0
        assert result.total_participants > 0
        assert len(result.top_meetings) <= 3
        assert 0.0 <= result.average_efficiency_score <= 1.0
        assert len(result.active_speakers) <= 10
        assert result.trending_keywords is not None

    @pytest.mark.asyncio
    async def test_get_project_overview_handles_empty_database(self):
        """빈 데이터베이스 처리."""
        service = EnhancedStatisticsService()

        from unittest.mock import MagicMock

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars

        db = AsyncMock()
        db.execute.return_value = mock_result

        redis_client = AsyncMock()

        result = await service.get_project_overview(
            period="30d",
            top_meetings=5,
            db=db,
            redis_client=redis_client,
        )

        assert result.total_meetings == 0
        assert result.total_duration_seconds == 0.0
        assert result.total_participants == 0
        assert result.average_efficiency_score == 0.0
        assert result.top_meetings == []
        assert result.active_speakers == []
        assert result.trending_keywords == []

    def test_generate_time_series_with_hourly_buckets_for_short_range(self):
        """짧은 기간(1일)에는 시간 단위 버킷."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 3600.0},  # 1 hour
            {"start": 3600.0, "end": 7200.0},  # 2nd hour
        ]

        time_series = service._generate_time_series(segments, "1d")

        assert len(time_series) <= 2
        for point in time_series:
            assert point.label == "1h"

    def test_generate_time_series_with_daily_buckets_for_long_range(self):
        """긴 기간(30일)에는 일 단위 버킷."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 86400.0},  # day 1
            {"start": 86400.0, "end": 172800.0},  # day 2
        ]

        time_series = service._generate_time_series(segments, "30d")

        assert len(time_series) <= 2
        for point in time_series:
            assert point.label == "1d"

    def test_analyze_speaker_patterns_with_multiple_speakers(self):
        """여러 화자의 참여도 패턴 분석."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0, "speaker": "Alice"},
            {"start": 30.0, "end": 60.0, "speaker": "Bob"},
            {"start": 60.0, "end": 90.0, "speaker": "Alice"},
            {"start": 90.0, "end": 120.0, "speaker": "Charlie"},
        ]

        patterns = service._analyze_speaker_patterns(segments)

        assert len(patterns) == 3
        assert patterns[0].speaker == "Alice"
        assert patterns[0].total_speaking_time == 60.0
        assert patterns[0].intervention_count == 2
        assert patterns[1].speaker == "Bob"
        assert patterns[1].total_speaking_time == 30.0

    def test_analyze_speaker_patterns_with_unknown_speaker(self):
        """알 수 없는 화자 처리."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0, "speaker": None},
            {"start": 30.0, "end": 60.0},
        ]

        patterns = service._analyze_speaker_patterns(segments)

        assert len(patterns) == 1
        assert patterns[0].speaker == "UNKNOWN"

    def test_analyze_keyword_trends_extracts_keywords(self):
        """키워드 빈도 추이 분석."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "text": "프로젝트 일정 확인"},
            {"start": 30.0, "text": "프로젝트 리스크 분석"},
            {"start": 60.0, "text": "일정 조정 필요"},
        ]

        trends = service._analyze_keyword_trends(segments, top_n=5)

        assert len(trends) > 0
        assert any(t.keyword == "프로젝트" for t in trends)
        assert any(t.keyword == "일정" for t in trends)
        for trend in trends:
            assert trend.total_count > 0
            assert trend.trend_direction in ["up", "down", "stable"]

    def test_calculate_efficiency_metrics_with_empty_segments(self):
        """빈 세그먼트 시 기본 효율성 지표 반환."""
        service = EnhancedStatisticsService()

        metrics = service._calculate_efficiency_metrics([])

        assert metrics.total_duration_seconds == 0.0
        assert metrics.effective_duration_seconds == 0.0
        assert metrics.silence_ratio == 0.0
        assert metrics.speaking_turn_count == 0
        assert metrics.average_turn_length == 0.0
        assert metrics.participation_balance == 0.0

    def test_calculate_efficiency_metrics_with_valid_segments(self):
        """유효한 세그먼트로 효율성 지표 계산."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0, "speaker": "A"},
            {"start": 30.0, "end": 60.0, "speaker": "B"},
            {"start": 60.0, "end": 90.0, "speaker": "A"},
        ]

        metrics = service._calculate_efficiency_metrics(segments)

        assert metrics.total_duration_seconds == 90.0
        assert metrics.effective_duration_seconds == 90.0
        assert metrics.silence_ratio == 0.0
        assert metrics.speaking_turn_count == 3
        assert metrics.average_turn_length == 30.0
        assert 0.0 <= metrics.participation_balance <= 1.0

    def test_calculate_efficiency_metrics_with_silence(self):
        """침묵 구간이 있는 효율성 지표 계산."""
        service = EnhancedStatisticsService()
        segments = [
            {"start": 0.0, "end": 30.0, "speaker": "A"},
            {"start": 60.0, "end": 90.0, "speaker": "B"},
        ]

        metrics = service._calculate_efficiency_metrics(segments)

        assert metrics.total_duration_seconds == 90.0
        assert metrics.effective_duration_seconds == 60.0
        assert metrics.silence_ratio > 0.3  # 30초 침묵 / 90초 전체
