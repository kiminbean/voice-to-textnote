"""
SPEC-STATS-001: 회의 통계 대시보드 API 테스트

- Redis 미스 → DB 폴백으로 minutes 결과 로드 후 통계 계산
- 화자 발화 시간/비율 합산
- 키워드 빈도 상위 top_n
- 존재하지 않는 task_id 는 404
"""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, TaskResult


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_engine(db_engine):
    """최소 minutes 결과 1건을 DB에 삽입한 엔진 반환."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    result_data = {
        "segments": [
            {
                "start": 0.0,
                "end": 4.0,
                "speaker": "SPEAKER_00",
                "text": "프로젝트 일정 검토 시작 합니다",
            },
            {
                "start": 4.0,
                "end": 9.0,
                "speaker": "SPEAKER_01",
                "text": "일정 조정 필요 프로젝트 진행 중",
            },
            {
                "start": 9.0,
                "end": 13.0,
                "speaker": "SPEAKER_00",
                "text": "프로젝트 리스크 공유",
            },
        ]
    }
    task = TaskResult(
        task_id="minutes-stats-001",
        task_type="minutes",
        status="completed",
        result_data=result_data,
    )
    async with session_factory() as session:
        session.add(task)
        await session.commit()
    return db_engine


def _make_app(db_engine) -> TestClient:
    from backend.app.api.v1.analytics.statistics import router
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    # Redis 미스 → DB 폴백 경로 테스트
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    async def override_redis():
        return redis_mock

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_redis_client] = override_redis
    return TestClient(app)


@pytest.fixture
def client(seeded_engine):
    return _make_app(seeded_engine)


@pytest.fixture
def empty_client(db_engine):
    return _make_app(db_engine)


class TestStatistics:
    def test_returns_200_and_schema(self, client):
        resp = client.get("/api/v1/statistics/minutes-stats-001")
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "task_id",
            "total_segments",
            "total_words",
            "total_duration_seconds",
            "unique_speakers",
            "speakers",
            "top_keywords",
        ):
            assert key in body

    def test_speaker_aggregation(self, client):
        body = client.get("/api/v1/statistics/minutes-stats-001").json()
        assert body["total_segments"] == 3
        assert body["unique_speakers"] == 2
        # 13초 총 발화 시간
        assert body["total_duration_seconds"] == pytest.approx(13.0, rel=1e-3)

        speakers = {s["speaker"]: s for s in body["speakers"]}
        assert set(speakers.keys()) == {"SPEAKER_00", "SPEAKER_01"}
        # SPEAKER_00 = 4 + 4 = 8초
        assert speakers["SPEAKER_00"]["speaking_time_seconds"] == pytest.approx(8.0)
        # SPEAKER_01 = 5초
        assert speakers["SPEAKER_01"]["speaking_time_seconds"] == pytest.approx(5.0)
        # 비율 합은 1.0 근사
        assert sum(s["speaking_ratio"] for s in body["speakers"]) == pytest.approx(
            1.0, rel=1e-3
        )

    def test_top_keywords_include_repeated_terms(self, client):
        body = client.get(
            "/api/v1/statistics/minutes-stats-001",
            params={"top_n": 5},
        ).json()
        keywords = {k["keyword"]: k["count"] for k in body["top_keywords"]}
        # "프로젝트" 는 3개 세그먼트에 모두 등장
        assert keywords.get("프로젝트", 0) >= 3
        # "일정" 은 2개 세그먼트에 등장
        assert keywords.get("일정", 0) >= 2

    def test_min_length_filter(self, client):
        body = client.get(
            "/api/v1/statistics/minutes-stats-001",
            params={"min_length": 3},
        ).json()
        for kw in body["top_keywords"]:
            assert len(kw["keyword"]) >= 3

    def test_missing_task_returns_404(self, empty_client):
        resp = empty_client.get("/api/v1/statistics/missing")
        assert resp.status_code == 404

    def test_invalid_top_n_returns_422(self, client):
        resp = client.get(
            "/api/v1/statistics/minutes-stats-001",
            params={"top_n": 0},
        )
        assert resp.status_code == 422


class TestStatisticsEmptySegments:
    """빈/비정상 세그먼트 처리 테스트"""

    def test_empty_segments_returns_zero_stats(self, db_engine):
        """세그먼트가 빈 배열이면 200 + zero 통계 반환"""
        import json
        client = _make_app_with_redis(db_engine, json.dumps({
            "status": "completed",
            "result": {"segments": []},
        }))
        resp = client.get("/api/v1/statistics/minutes-stats-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_segments"] == 0
        assert body["total_words"] == 0

    def test_non_dict_and_invalid_segments_skipped(self, db_engine):
        """비정상 세그먼트가 있으면 무시하고 정상 항목만 집계"""
        import json
        client = _make_app_with_redis(db_engine, json.dumps({
            "status": "completed",
            "result": {
                "segments": [
                    "not_a_dict",
                    42,
                    {"start": "abc", "end": "xyz", "text": "bad"},
                    {"start": 0, "end": 10, "text": "good"},
                ]
            },
        }))
        resp = client.get("/api/v1/statistics/minutes-stats-001")
        assert resp.status_code == 200
        # 비정상 세그먼트가 모두 무시되었는지 확인 (total_segments ≤ 1)
        body = resp.json()
        assert body["total_segments"] <= 1


def _make_app_with_redis(db_engine, redis_data: str) -> TestClient:
    """커스텀 Redis 데이터로 TestClient 생성"""
    from backend.app.api.v1.analytics.statistics import router
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    redis_mock = AsyncMock()
    redis_mock.get.return_value = redis_data

    async def override_redis():
        return redis_mock

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_redis_client] = override_redis

    return TestClient(app)
