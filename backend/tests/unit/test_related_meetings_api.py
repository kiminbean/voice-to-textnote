"""
관련 회의 추천 API 테스트 - SPEC-RELATED-001

테스트 범위:
- GET /api/v1/related-meetings/{task_id}: 관련 회의 추천 엔드포인트
- 정상 응답, limit 상한 검증(422), 미존재/무관 회의 처리
"""

from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.config import settings
from backend.app.error_handlers import register_exception_handlers
from backend.db.models import Base, TaskResult

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index "
                "USING fts5(task_id, task_type, content, speaker_names, "
                "summary_text, action_items_text, created_at UNINDEXED, "
                "tokenize='unicode61')"
            )
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def populated_db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        rows = [
            (
                "api-src-001",
                "minutes",
                "백엔드 API 설계 회의. 데이터베이스 스키마 인덱스 최적화를 논의했습니다.",
                "2024-01-01T09:00:00",
            ),
            (
                "api-rel-001",
                "minutes",
                "백엔드 API 설계 리뷰와 데이터베이스 인덱스 튜닝을 진행했습니다.",
                "2024-01-02T09:00:00",
            ),
        ]
        for task_id, task_type, content, created_at in rows:
            session.add(
                TaskResult(
                    task_id=task_id,
                    task_type=task_type,
                    status="completed",
                    result_data={},
                    completed_at=datetime.fromisoformat(created_at),
                )
            )
        await session.flush()
        for task_id, task_type, content, created_at in rows:
            await session.execute(
                text(
                    "INSERT INTO search_index "
                    "(task_id, task_type, content, speaker_names, summary_text, "
                    "action_items_text, created_at) VALUES "
                    "(:task_id, :task_type, :content, '', '', '', :created_at)"
                ),
                {
                    "task_id": task_id,
                    "task_type": task_type,
                    "content": content,
                    "created_at": created_at,
                },
            )
        await session.commit()
    yield db_engine


@pytest.fixture
def client(populated_db):
    """related-meetings 라우터만 포함한 TestClient"""
    from backend.app.api.v1.analytics.related_meetings import router
    from backend.app.dependencies import get_db_session

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(populated_db, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestRelatedMeetingsAPI:
    def test_returns_200_with_related(self, client):
        resp = client.get("/api/v1/related-meetings/api-src-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_task_id"] == "api-src-001"
        assert data["keywords"]
        returned = {item["task_id"] for item in data["items"]}
        assert "api-src-001" not in returned
        assert "api-rel-001" in returned
        assert data["total"] == len(data["items"])

    def test_related_item_shape(self, client):
        resp = client.get("/api/v1/related-meetings/api-src-001")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items, "관련 회의가 하나 이상 있어야 한다"
        item = items[0]
        assert set(item) >= {
            "task_id",
            "task_type",
            "snippet",
            "shared_keywords",
            "score",
            "created_at",
        }
        assert 0.0 <= item["score"] <= 1.0
        assert isinstance(item["shared_keywords"], list)

    def test_limit_over_max_returns_422(self, client):
        over = settings.related_meetings_max_limit + 1
        resp = client.get(
            "/api/v1/related-meetings/api-src-001", params={"limit": over}
        )
        assert resp.status_code == 422

    def test_limit_zero_returns_422(self, client):
        """limit은 1 이상이어야 한다 (Query ge=1)."""
        resp = client.get(
            "/api/v1/related-meetings/api-src-001", params={"limit": 0}
        )
        assert resp.status_code == 422

    def test_unknown_task_returns_empty(self, client):
        """인증 컨텍스트 없이 미존재 task는 빈 결과(200)를 반환한다."""
        resp = client.get("/api/v1/related-meetings/no-such-task")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_limit_respected(self, client):
        resp = client.get(
            "/api/v1/related-meetings/api-src-001", params={"limit": 1}
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 1
