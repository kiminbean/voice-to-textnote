"""
검색 API 테스트 - SPEC-SEARCH-001

테스트 범위:
- GET /api/v1/search: FTS5 기반 전문 검색 API (REQ-SEARCH-001~005)
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base


# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """인메모리 SQLite 비동기 엔진 픽스처"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # FTS5 테이블 생성
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
async def db_session(db_engine):
    """비동기 DB 세션 픽스처"""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def populated_db(db_session: AsyncSession):
    """테스트 데이터 삽입 픽스처"""
    from datetime import datetime

    from backend.db.models import TaskResult

    records = [
        TaskResult(
            task_id="search-min-001",
            task_type="minutes",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 1, 9, 0, 0),
        ),
        TaskResult(
            task_id="search-sum-001",
            task_type="summary",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 2, 9, 0, 0),
        ),
    ]
    for r in records:
        db_session.add(r)
    await db_session.flush()

    # 검색 인덱스 데이터 삽입
    rows = [
        {
            "task_id": "search-min-001",
            "task_type": "minutes",
            "content": "오늘 회의를 진행했습니다. 프로젝트 일정을 논의했습니다.",
            "speaker_names": "김팀장 이개발",
            "summary_text": "",
            "action_items_text": "",
            "created_at": "2024-01-01T09:00:00",
        },
        {
            "task_id": "search-sum-001",
            "task_type": "summary",
            "content": "",
            "speaker_names": "",
            "summary_text": "회의 결과 FastAPI 도입을 결정했습니다.",
            "action_items_text": "보고서 작성 완료",
            "created_at": "2024-01-02T09:00:00",
        },
    ]
    for row in rows:
        await db_session.execute(
            text(
                "INSERT INTO search_index "
                "(task_id, task_type, content, speaker_names, summary_text, action_items_text, created_at) "
                "VALUES (:task_id, :task_type, :content, :speaker_names, :summary_text, :action_items_text, :created_at)"
            ),
            row,
        )
    await db_session.commit()
    yield db_session


@pytest.fixture
def test_app(db_engine):
    """테스트용 FastAPI 앱 픽스처 (search 라우터만 포함)"""
    from backend.app.api.v1.search import router
    from backend.app.dependencies import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return app


@pytest.fixture
def client(test_app, populated_db):
    """데이터가 삽입된 TestClient"""
    return TestClient(test_app)


@pytest.fixture
def empty_client(test_app):
    """빈 DB의 TestClient"""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# 검색 API 테스트
# ---------------------------------------------------------------------------


class TestSearchAPI:
    """GET /api/v1/search 테스트"""

    def test_search_returns_200_with_results(self, client):
        """검색 결과가 있을 때 200 반환해야 함"""
        resp = client.get("/api/v1/search", params={"q": "회의"})
        assert resp.status_code == 200

    def test_search_missing_q_returns_422(self, client):
        """q 파라미터가 없으면 422 반환해야 함"""
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422

    def test_search_short_q_returns_422(self, client):
        """q가 1글자이면 422 반환해야 함 (min_length=2)"""
        resp = client.get("/api/v1/search", params={"q": "가"})
        assert resp.status_code == 422

    def test_search_empty_q_returns_422(self, client):
        """q가 빈 문자열이면 422 반환해야 함"""
        resp = client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 422

    def test_search_whitespace_q_returns_422(self, client):
        """q가 공백만 있으면 422 반환해야 함"""
        resp = client.get("/api/v1/search", params={"q": "   "})
        assert resp.status_code == 422

    def test_search_invalid_task_type_returns_422(self, client):
        """유효하지 않은 task_type은 422 반환해야 함"""
        resp = client.get("/api/v1/search", params={"q": "회의", "task_type": "invalid"})
        assert resp.status_code == 422

    def test_search_pagination_works(self, client):
        """페이지네이션 파라미터가 동작해야 함"""
        resp = client.get(
            "/api/v1/search",
            params={"q": "회의", "page": 1, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_search_task_type_filter_summary(self, client):
        """task_type=summary 필터가 동작해야 함"""
        resp = client.get(
            "/api/v1/search",
            params={"q": "FastAPI", "task_type": "summary"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["task_type"] == "summary"

    def test_search_task_type_filter_minutes(self, client):
        """task_type=minutes 필터가 동작해야 함"""
        resp = client.get(
            "/api/v1/search",
            params={"q": "프로젝트", "task_type": "minutes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["task_type"] == "minutes"

    def test_search_no_results_returns_empty(self, client):
        """매칭 없는 쿼리는 빈 items와 total=0 반환해야 함"""
        resp = client.get(
            "/api/v1/search",
            params={"q": "존재하지않는내용xyz99999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_response_schema(self, client):
        """응답이 SearchResponse 스키마를 따라야 함"""
        resp = client.get("/api/v1/search", params={"q": "회의"})
        assert resp.status_code == 200
        data = resp.json()

        # 필수 필드 확인
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "query" in data
        assert data["query"] == "회의"

    def test_search_result_item_schema(self, client):
        """SearchResultItem이 올바른 필드를 포함해야 함"""
        resp = client.get("/api/v1/search", params={"q": "회의"})
        assert resp.status_code == 200
        data = resp.json()

        if data["items"]:
            item = data["items"][0]
            assert "task_id" in item
            assert "task_type" in item
            assert "snippet" in item
            assert "created_at" in item
            # completed_at은 optional (None 가능)
            assert "completed_at" in item

    def test_search_task_type_all_default(self, client):
        """task_type 기본값은 'all'이어야 함"""
        resp = client.get("/api/v1/search", params={"q": "회의"})
        assert resp.status_code == 200

    def test_search_page_size_limit(self, client):
        """page_size 최대값은 50이어야 함"""
        resp = client.get(
            "/api/v1/search",
            params={"q": "회의", "page_size": 100},
        )
        # 최대값 초과는 422
        assert resp.status_code == 422
