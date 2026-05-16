"""
SPEC-BOOKMARK-001: 북마크/하이라이트 API 기본 테스트

CRUD 기본 흐름, 소유권 격리, 입력 검증을 커버한다.
JWT 의존성은 테스트에서 override하여 고정 유저로 대체한다.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - Base 메타데이터 등록용
import backend.db.bookmark_models  # noqa: F401
from backend.db.auth_models import User
from backend.db.models import Base, TaskResult

# ---------------------------------------------------------------------------
# 공용 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db_engine):
    """테스트용 user / task_result 1건씩 삽입."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    user_a = User()
    user_a.id = uuid.uuid4()
    user_a.email = "a@example.com"
    user_a.password_hash = "x"
    user_a.display_name = "A"
    user_a.is_active = True

    user_b = User()
    user_b.id = uuid.uuid4()
    user_b.email = "b@example.com"
    user_b.password_hash = "x"
    user_b.display_name = "B"
    user_b.is_active = True

    task = TaskResult(
        task_id="minutes-test-001",
        task_type="minutes",
        status="completed",
        result_data={"segments": [{"start": 0, "end": 5, "text": "안녕"}]},
    )

    async with session_factory() as session:
        session.add_all([user_a, user_b, task])
        await session.commit()

    return {"user_a": user_a, "user_b": user_b, "task_id": task.task_id}


def _make_app(db_engine, acting_user: User) -> FastAPI:
    """엔드포인트와 JWT 의존성을 mock 한 테스트 앱 생성."""
    from backend.app.api.v1.bookmarks import router
    from backend.app.dependencies import get_current_user, get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    async def override_current_user():
        return acting_user

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@pytest.fixture
def client_a(db_engine, seeded_db):
    app = _make_app(db_engine, seeded_db["user_a"])
    return TestClient(app), seeded_db


@pytest.fixture
def client_b(db_engine, seeded_db):
    app = _make_app(db_engine, seeded_db["user_b"])
    return TestClient(app), seeded_db


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestBookmarkCreate:
    def test_create_returns_201(self, client_a):
        client, seed = client_a
        resp = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 5.0,
                "note": "첫 발언",
                "color": "#ff0000",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["task_id"] == seed["task_id"]
        assert body["segment_end"] == 5.0
        assert body["note"] == "첫 발언"
        assert body["color"] == "#ff0000"
        assert "id" in body and "user_id" in body

    def test_create_rejects_invalid_range(self, client_a):
        client, seed = client_a
        resp = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 10.0,
                "segment_end": 5.0,
            },
        )
        assert resp.status_code == 422

    def test_create_rejects_unknown_task(self, client_a):
        client, _ = client_a
        resp = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": "does-not-exist",
                "segment_start": 0.0,
                "segment_end": 1.0,
            },
        )
        assert resp.status_code == 404

    def test_create_rejects_invalid_color(self, client_a):
        client, seed = client_a
        resp = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 1.0,
                "color": "!!",
            },
        )
        assert resp.status_code == 422


class TestBookmarkListGetDelete:
    def test_owner_can_list_and_read(self, client_a):
        client, seed = client_a
        created = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 2.0,
                "note": "hi",
            },
        ).json()

        lst = client.get("/api/v1/bookmarks").json()
        assert lst["total"] == 1
        assert lst["items"][0]["id"] == created["id"]

        single = client.get(f"/api/v1/bookmarks/{created['id']}")
        assert single.status_code == 200
        assert single.json()["note"] == "hi"

    def test_filter_by_task_id(self, client_a):
        client, seed = client_a
        client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 1.0,
            },
        )
        resp = client.get(
            "/api/v1/bookmarks",
            params={"task_id": seed["task_id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp_empty = client.get(
            "/api/v1/bookmarks",
            params={"task_id": "other"},
        )
        assert resp_empty.json()["total"] == 0

    def test_non_owner_cannot_read(self, db_engine, seeded_db):
        # A가 북마크 생성
        app_a = _make_app(db_engine, seeded_db["user_a"])
        client_a = TestClient(app_a)
        created = client_a.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seeded_db["task_id"],
                "segment_start": 0.0,
                "segment_end": 1.0,
            },
        ).json()
        # B로 읽기 시도
        app_b = _make_app(db_engine, seeded_db["user_b"])
        client_b = TestClient(app_b)
        resp = client_b.get(f"/api/v1/bookmarks/{created['id']}")
        assert resp.status_code == 404

    def test_update_patch(self, client_a):
        client, seed = client_a
        created = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 2.0,
                "note": "old",
            },
        ).json()
        resp = client.patch(
            f"/api/v1/bookmarks/{created['id']}",
            json={"note": "new", "color": "blue"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["note"] == "new"
        assert body["color"] == "blue"
        # 미변경 필드 유지
        assert body["segment_end"] == 2.0

    def test_delete(self, client_a):
        client, seed = client_a
        created = client.post(
            "/api/v1/bookmarks",
            json={
                "task_id": seed["task_id"],
                "segment_start": 0.0,
                "segment_end": 1.0,
            },
        ).json()
        r = client.delete(f"/api/v1/bookmarks/{created['id']}")
        assert r.status_code == 204
        r2 = client.get(f"/api/v1/bookmarks/{created['id']}")
        assert r2.status_code == 404
