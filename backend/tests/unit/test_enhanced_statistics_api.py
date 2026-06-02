"""
SPEC-ENHANCED-STATS-001: 고급 통계 대시보드 API 테스트

고급 통계 엔드포인트 테스트:
- GET /api/v1/enhanced-statistics/{task_id}
- GET /api/v1/enhanced-statistics/overview
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, TaskResult


@pytest.fixture
async def db_engine():
    """테스트용 DB 엔진."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_engine(db_engine):
    """테스트 데이터가 포함된 엔진."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    # 테스트용 회의록 데이터
    result_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 30.0,
                "speaker": "SPEAKER_00",
                "text": "프로젝트 일정 검토 시작 합니다 프로젝트 리스크 공유",
            },
            {
                "start": 30.0,
                "end": 60.0,
                "speaker": "SPEAKER_01",
                "text": "일정 조정 필요 프로젝트 진행 중 일정 확인",
            },
            {
                "start": 60.0,
                "end": 90.0,
                "speaker": "SPEAKER_00",
                "text": "프로젝트 마일스톤 설정 프로젝트 목표",
            },
            {
                "start": 90.0,
                "end": 120.0,
                "speaker": "SPEAKER_02",
                "text": "리스크 관리 계획 프로젝트 위험 요소",
            },
        ]
    }

    task = TaskResult(
        task_id="enhanced-stats-001",
        task_type="minutes",
        status="completed",
        result_data=result_data,
    )

    async with session_factory() as session:
        session.add(task)
        await session.commit()

    return db_engine


def _make_app(db_engine, redis_mock=None) -> TestClient:
    """테스트용 FastAPI 앱 생성."""
    from backend.app.api.v1.enhanced_statistics import router
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    if redis_mock is None:
        # 기본 Redis 미스 mock
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

    async def override_redis():
        return redis_mock

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_redis_client] = override_redis

    return TestClient(app)


@pytest.fixture
def client(seeded_engine):
    """데이터가 포함된 클라이언트."""
    return _make_app(seeded_engine)


@pytest.fixture
def empty_client(db_engine):
    """빈 데이터베이스 클라이언트."""
    return _make_app(db_engine)


class TestEnhancedStatistics:
    """고급 통계 엔드포인트 테스트."""

    def test_returns_200_and_valid_schema(self, client):
        """200 응답과 유효한 스키마 반환."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        assert resp.status_code == 200

        body = resp.json()
        required_fields = [
            "task_id",
            "time_range",
            "time_series",
            "speaker_patterns",
            "keyword_trends",
            "efficiency_metrics",
            "metadata",
        ]
        for field in required_fields:
            assert field in body

    def test_task_id_matches_request(self, client):
        """task_id가 요청과 일치."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        body = resp.json()
        assert body["task_id"] == "enhanced-stats-001"

    def test_default_time_range_is_7d(self, client):
        """기본 time_range는 7d."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        body = resp.json()
        assert body["time_range"] == "7d"

    def test_custom_time_range_accepted(self, client):
        """커스텀 time_range 적용."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"time_range": "30d"},
        )
        body = resp.json()
        assert body["time_range"] == "30d"

    def test_invalid_time_range_returns_422(self, client):
        """잘못된 time_range는 422."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"time_range": "invalid"},
        )
        assert resp.status_code == 422

    def test_top_n_keywords_parameter(self, client):
        """top_n_keywords 파라미터 적용."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"top_n_keywords": 5},
        )
        body = resp.json()
        assert len(body["keyword_trends"]) <= 5

    def test_invalid_top_n_returns_422(self, client):
        """잘못된 top_n은 422."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"top_n_keywords": 0},
        )
        assert resp.status_code == 422

    def test_missing_task_returns_404(self, empty_client):
        """존재하지 않는 task_id는 404."""
        resp = empty_client.get("/api/v1/enhanced-statistics/missing-task")
        assert resp.status_code == 404

    def test_empty_segments_returns_warning(self, db_engine):
        """빈 세그먼트는 경고와 빈 데이터 반환."""
        import json

        redis_mock = AsyncMock()
        redis_mock.get.return_value = json.dumps(
            {"status": "completed", "result": {"segments": []}}
        )

        client = _make_app(db_engine, redis_mock)
        resp = client.get("/api/v1/enhanced-statistics/test-task")

        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["warning"] == "세그먼트 데이터가 없습니다."
        assert body["time_series"] == []
        assert body["speaker_patterns"] == []


class TestSpeakerPatterns:
    """화자별 참여도 패턴 테스트."""

    def test_speaker_patterns_include_required_fields(self, client):
        """화자 패턴에 필수 필드 포함."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        body = resp.json()

        assert len(body["speaker_patterns"]) > 0
        pattern = body["speaker_patterns"][0]
        assert "speaker" in pattern
        assert "total_speaking_time" in pattern
        assert "participation_rate" in pattern
        assert "average_segment_length" in pattern
        assert "intervention_count" in pattern
        assert "most_active_hour" in pattern

    def test_speaker_patterns_sorted_by_duration(self, client):
        """화자 패턴이 발화 시간 기준 정렬."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        body = resp.json()

        durations = [p["total_speaking_time"] for p in body["speaker_patterns"]]
        assert durations == sorted(durations, reverse=True)

    def test_participation_rates_sum_to_approximately_one(self, client):
        """참여율 합이 1에 근접."""
        resp = client.get("/api/v1/enhanced-statistics/enhanced-stats-001")
        body = resp.json()

        total_rate = sum(p["participation_rate"] for p in body["speaker_patterns"])
        assert abs(total_rate - 1.0) < 0.01


class TestEfficiencyMetrics:
    """효율성 지표 테스트."""

    def test_efficiency_metrics_include_required_fields(self, client):
        """효율성 지표에 필수 필드 포함."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"include_efficiency_metrics": True},
        )
        body = resp.json()

        assert body["efficiency_metrics"] is not None
        metrics = body["efficiency_metrics"]
        assert "total_duration_seconds" in metrics
        assert "effective_duration_seconds" in metrics
        assert "silence_ratio" in metrics
        assert "speaking_turn_count" in metrics
        assert "average_turn_length" in metrics
        assert "participation_balance" in metrics

    def test_efficiency_metrics_can_be_disabled(self, client):
        """효율성 지표 비활성화 가능."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"include_efficiency_metrics": False},
        )
        body = resp.json()

        assert body["efficiency_metrics"] is None

    def test_efficiency_metrics_values_in_valid_ranges(self, client):
        """효율성 지표 값이 유효 범위 내."""
        resp = client.get(
            "/api/v1/enhanced-statistics/enhanced-stats-001",
            params={"include_efficiency_metrics": True},
        )
        body = resp.json()

        metrics = body["efficiency_metrics"]
        assert 0 <= metrics["silence_ratio"] <= 1
        assert 0 <= metrics["participation_balance"] <= 1
        assert metrics["speaking_turn_count"] >= 0
        assert metrics["average_turn_length"] >= 0


