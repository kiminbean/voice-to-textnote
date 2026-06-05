"""
자동 키워드 API 테스트.
"""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - Base 메타데이터 등록용
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
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    records = [
        TaskResult(
            task_id="minutes-keyword-001",
            task_type="minutes",
            status="completed",
            result_data={
                "segments": [
                    {
                        "start": 0.0,
                        "end": 3.0,
                        "speaker": "SPEAKER_00",
                        "text": "프로젝트 일정과 FastAPI API 성능을 검토했습니다.",
                    },
                    {
                        "start": 3.0,
                        "end": 7.0,
                        "speaker": "SPEAKER_01",
                        "text": "Redis 캐시 전략과 API 배포 리스크를 논의했습니다.",
                    },
                ]
            },
        ),
        TaskResult(
            task_id="minutes-keyword-history-001",
            task_type="minutes",
            status="completed",
            result_data={
                "segments": [
                    {
                        "start": 0.0,
                        "end": 4.0,
                        "speaker": "SPEAKER_00",
                        "text": "이전 회의에서 API 배포 전략과 Redis TTL 조정을 논의했습니다.",
                    },
                ]
            },
        ),
    ]
    async with session_factory() as session:
        session.add_all(records)
        await session.commit()
    return db_engine


def _make_app(db_engine) -> TestClient:
    from backend.app.api.v1.minutes.keywords import router
    from backend.app.dependencies import get_db_session, get_redis_client

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True

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


class TestKeywordsAPI:
    def test_extract_from_text(self, client):
        resp = client.post(
            "/api/v1/keywords/extract",
            json={
                "text": (
                    "프로젝트 일정 검토와 FastAPI API 성능 개선을 논의했습니다. "
                    "Redis 캐시 전략도 함께 검토했습니다."
                ),
                "max_keywords": 8,
                "min_score": 0.0,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "text"
        assert body["total_count"] > 0
        assert body["groups"]
        assert all(0.0 <= item["score"] <= 1.0 for item in body["keywords"])

    def test_get_keywords_for_existing_meeting(self, client):
        resp = client.get(
            "/api/v1/keywords/minutes-keyword-001",
            params={"max_keywords": 10, "min_score": 0.0},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "minutes-keyword-001"
        assert body["source"] == "meeting"
        assert body["total_count"] > 0

    def test_recommend_keywords_uses_history(self, client):
        resp = client.post(
            "/api/v1/keywords/minutes-keyword-001/recommend",
            json={"max_keywords": 10, "min_score": 0.0, "history_limit": 5},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "history_recommendation"
        assert body["history_task_count"] == 1
        assert body["total_count"] > 0
        assert any(item["source"] in {"current+history", "history"} for item in body["keywords"])

    def test_missing_meeting_returns_404(self, empty_client):
        resp = empty_client.get("/api/v1/keywords/missing-task")
        assert resp.status_code == 404

    def test_invalid_extract_text_returns_422(self, client):
        resp = client.post("/api/v1/keywords/extract", json={"text": "short"})
        assert resp.status_code == 422
