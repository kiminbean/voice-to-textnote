"""EfficiencyService behavior and coverage tests."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.schemas.efficiency import (
    ActionItemMetric,
    DecisionMetric,
    EfficiencyMetrics,
    KeywordMetric,
    ParticipationMetric,
    TimeDistributionMetric,
)
from backend.services.efficiency_service import EfficiencyService


def _segments() -> list[dict]:
    return [
        {
            "speaker": "alice",
            "text": "이번 안건은 출시 여부를 결정하고 실행 계획을 시작해야 합니다 good",
            "start_time": 0,
            "end_time": 60,
        },
        {
            "speaker": "bob",
            "text": "좋다 다음 마감 작업을 공유하고 완료 기준을 검토합니다",
            "start_time": 90,
            "end_time": 150,
        },
        {
            "speaker": "alice",
            "text": "문제 없이 승인되면 담당자가 행동 항목을 처리합니다",
            "start_time": 180,
            "end_time": 240,
        },
    ]


def _db_result(*, first=None, all_items=None):
    scalars = MagicMock()
    scalars.first.return_value = first
    scalars.all.return_value = all_items or []
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _action_item(description: str | None):
    item = MagicMock()
    item.id = uuid.uuid4()
    item.description = description
    return item


@pytest.mark.asyncio
async def test_get_minutes_data_prefers_redis_cache():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    payload = {"segments": _segments()}
    redis_client.get.return_value = json.dumps(payload)

    result = await service._get_minutes_data(redis_client, db, "task-1")

    assert result == payload
    redis_client.get.assert_awaited_once_with("task:min:result:task-1")
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_minutes_data_uses_completed_db_fallback():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = None
    record = MagicMock(result_data={"segments": _segments()})
    db.execute.return_value = _db_result(first=record)

    result = await service._get_minutes_data(redis_client, db, "task-2")

    assert result == {"segments": _segments()}
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_minutes_data_returns_none_when_cache_and_db_miss():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = None
    db.execute.return_value = _db_result(first=None)

    assert await service._get_minutes_data(redis_client, db, "missing") is None


@pytest.mark.asyncio
async def test_analyze_meeting_efficiency_detailed_with_recommendations():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = json.dumps({"segments": _segments()})
    db.execute.return_value = _db_result(
        all_items=[
            _action_item("출시 체크리스트를 작성하고 담당자를 지정한다"),
            _action_item("짧음"),
        ]
    )

    result = await service.analyze_meeting_efficiency(
        redis_client=redis_client,
        db=db,
        task_id="task-3",
        include_recommendations=True,
        min_speakers=2,
        analysis_depth="detailed",
    )

    assert result.task_id == "task-3"
    assert result.total_speakers == 2
    assert result.total_segments == 3
    assert result.meeting_duration_minutes == 4
    assert result.efficiency_metrics.sentiment_trend is not None
    assert result.efficiency_metrics.keyword_metric.total_keywords > 0
    assert result.efficiency_metrics.action_item_metric.total_action_items == 2
    assert result.recommendations is not None


@pytest.mark.asyncio
async def test_analyze_meeting_efficiency_can_skip_recommendations():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = json.dumps({"segments": _segments()})
    db.execute.return_value = _db_result(all_items=[])

    result = await service.analyze_meeting_efficiency(
        redis_client=redis_client,
        db=db,
        task_id="task-4",
        include_recommendations=False,
        min_speakers=1,
        analysis_depth="basic",
    )

    assert result.recommendations is None
    assert result.efficiency_metrics.sentiment_trend is None


@pytest.mark.asyncio
async def test_analyze_meeting_efficiency_rejects_missing_minutes_data():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = None
    db.execute.return_value = _db_result(first=None)

    with pytest.raises(ValueError, match="회의록 데이터를 찾을 수 없습니다"):
        await service.analyze_meeting_efficiency(redis_client, db, "missing")


@pytest.mark.asyncio
async def test_analyze_meeting_efficiency_rejects_empty_segments():
    service = EfficiencyService()
    redis_client = AsyncMock()
    db = AsyncMock()
    redis_client.get.return_value = json.dumps({"segments": []})

    with pytest.raises(ValueError, match="segments 정보가 없습니다"):
        await service.analyze_meeting_efficiency(redis_client, db, "empty")


def test_metric_helpers_cover_empty_and_single_speaker_paths():
    service = EfficiencyService()

    assert service._calculate_basic_metrics([], "standard") == {}
    assert service._analyze_participation(_segments()[:1], min_speakers=2) == []

    empty_time = service._analyze_time_distribution([], "standard")
    assert empty_time.total_meeting_duration_minutes == 0
    assert empty_time.agenda_adherence_score == 0.5

    single_time = service._analyze_time_distribution(_segments()[:1], "standard")
    assert single_time.agenda_adherence_score == 0.5
    assert single_time.time_efficiency_score == 1


def test_sentiment_trend_branches():
    service = EfficiencyService()

    improving = service._analyze_sentiment(
        [
            {"text": "문제 bad problem"},
            {"text": "좋다 excellent great good"},
        ]
    )
    declining = service._analyze_sentiment(
        [
            {"text": "좋다 excellent great good"},
            {"text": "문제 bad problem"},
        ]
    )
    stable = service._analyze_sentiment([{"text": "plain words"}, {"text": "plain words"}])

    assert improving is not None and improving.sentiment_trend == "improving"
    assert declining is not None and declining.sentiment_trend == "declining"
    assert stable is not None and stable.sentiment_trend == "stable"
    assert service._analyze_sentiment([]) is None


def test_efficiency_score_grade_thresholds():
    service = EfficiencyService()
    keyword = KeywordMetric(
        total_keywords=1,
        unique_keywords=1,
        keyword_diversity_score=1,
        action_keywords_count=0,
        decision_keywords_count=1,
    )

    cases = [
        (1.0, "A"),
        (0.8, "B"),
        (0.7, "C"),
        (0.6, "D"),
        (0.0, "F"),
    ]
    for score, grade in cases:
        participation = [
            ParticipationMetric(
                speaker_id="a",
                speaker_name="a",
                speaking_time_seconds=60,
                speaking_percentage=50,
                segment_count=1,
                avg_segment_length=60,
                participation_balance_score=score,
            )
        ]
        result = service._calculate_efficiency_score(
            participation_metrics=participation,
            decision_metric=DecisionMetric(
                total_decisions=1,
                decisions_per_hour=5,
                avg_decision_time_minutes=1,
                decision_clarity_score=score,
            ),
            action_item_metric=ActionItemMetric(
                total_action_items=1,
                action_items_per_hour=3,
                action_item_clarity_score=score,
            ),
            time_distribution=TimeDistributionMetric(
                total_meeting_duration_minutes=1,
                actual_speaking_time_minutes=score,
                silence_percentage=0,
                agenda_adherence_score=1,
                time_efficiency_score=score,
            ),
            keyword_metric=keyword,
        )

        assert result.efficiency_grade == grade


def test_efficiency_score_without_participation_metrics_defaults_to_zero_balance():
    service = EfficiencyService()

    result = service._calculate_efficiency_score(
        participation_metrics=[],
        decision_metric=DecisionMetric(
            total_decisions=0,
            decisions_per_hour=0,
            avg_decision_time_minutes=0,
            decision_clarity_score=0,
        ),
        action_item_metric=ActionItemMetric(
            total_action_items=0,
            action_items_per_hour=0,
            action_item_clarity_score=0,
        ),
        time_distribution=TimeDistributionMetric(
            total_meeting_duration_minutes=0,
            actual_speaking_time_minutes=0,
            silence_percentage=0,
            agenda_adherence_score=0.5,
            time_efficiency_score=0,
        ),
        keyword_metric=KeywordMetric(
            total_keywords=0,
            unique_keywords=0,
            keyword_diversity_score=0,
            action_keywords_count=0,
            decision_keywords_count=0,
        ),
    )

    assert result.participation_balance == 0
    assert result.efficiency_grade == "F"


def test_recommendations_cover_all_categories_and_quick_wins():
    service = EfficiencyService()
    participation = [
        ParticipationMetric(
            speaker_id="quiet",
            speaker_name="quiet",
            speaking_time_seconds=5,
            speaking_percentage=5,
            segment_count=1,
            avg_segment_length=5,
            participation_balance_score=0.2,
        )
    ]
    metrics = EfficiencyMetrics(
        participation_balance=0.2,
        time_efficiency=0.4,
        decision_effectiveness=0.3,
        action_item_quality=0.2,
        overall_efficiency_score=0.3,
        efficiency_grade="F",
        participation_metrics=participation,
        decision_metric=DecisionMetric(
            total_decisions=0,
            decisions_per_hour=0,
            avg_decision_time_minutes=0,
            decision_clarity_score=0,
        ),
        action_item_metric=ActionItemMetric(
            total_action_items=0,
            action_items_per_hour=0,
            action_item_clarity_score=0,
        ),
        time_distribution=TimeDistributionMetric(
            total_meeting_duration_minutes=10,
            actual_speaking_time_minutes=4,
            silence_percentage=60,
            agenda_adherence_score=0.5,
            time_efficiency_score=0.4,
        ),
        keyword_metric=KeywordMetric(
            total_keywords=0,
            unique_keywords=0,
            keyword_diversity_score=0,
            action_keywords_count=0,
            decision_keywords_count=0,
        ),
    )

    recommendations = service._generate_recommendations(
        metrics,
        participation,
        metrics.time_distribution,
        "detailed",
    )

    assert recommendations.total_recommendations == 5
    assert recommendations.participation_recommendations
    assert recommendations.time_recommendations
    assert recommendations.decision_recommendations
    assert recommendations.action_item_recommendations
    assert recommendations.general_recommendations
    assert "라운드식 발화 기회 제공" in recommendations.quick_wins
