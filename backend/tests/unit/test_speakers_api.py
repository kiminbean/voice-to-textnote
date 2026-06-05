"""
SPEC-SPEAKER-001: 화자 프로필 API 기본 테스트

CRUD 기본 흐름, 소유권 격리, 입력 검증, 중복 방지를 커버한다.
JWT 의존성은 테스트에서 override하여 고정 유저로 대체한다.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - Base 메타데이터 등록용
import backend.db.speaker_models  # noqa: F401
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
    """테스트용 user / task_result 삽입."""
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
        task_id="dia-test-001",
        task_type="diarization",
        status="completed",
        result_data={"segments": []},
    )

    async with session_factory() as session:
        session.add_all([user_a, user_b, task])
        await session.commit()

    return {"user_a": user_a, "user_b": user_b, "task_id": task.task_id}


def _make_app(db_engine, acting_user: User) -> FastAPI:
    from backend.app.api.v1.collaboration.speakers import router
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


# ---------------------------------------------------------------------------
# 생성 (POST /api/v1/speakers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_speaker_global(db_engine, seeded_db):
    """전역 화자 프로필 생성."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "김철수"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["speaker_label"] == "SPEAKER_00"
    assert body["display_name"] == "김철수"
    assert body["task_id"] is None  # 전역 프로필


@pytest.mark.asyncio
async def test_create_speaker_per_meeting(db_engine, seeded_db):
    """회의록별 화자 프로필 생성."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/speakers",
            json={
                "speaker_label": "SPEAKER_00",
                "display_name": "이영희",
                "role": "팀장",
                "task_id": seeded_db["task_id"],
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["task_id"] == seeded_db["task_id"]
    assert body["role"] == "팀장"


@pytest.mark.asyncio
async def test_create_speaker_duplicate_rejected(db_engine, seeded_db):
    """동일 (user, label, task_id) 조합 중복 생성 시 409."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_01", "display_name": "홍길동"},
        )
        resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_01", "display_name": "다른 이름"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_speaker_validation_empty_label(db_engine, seeded_db):
    """빈 speaker_label은 422."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "", "display_name": "테스트"},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 목록 (GET /api/v1/speakers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_speakers_empty(db_engine, seeded_db):
    """프로필 없을 때 빈 목록 반환."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        resp = client.get("/api/v1/speakers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_list_speakers_filter_by_task_id(db_engine, seeded_db):
    """task_id 필터링 시 전역 + 해당 회의록 프로필 반환."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        # 전역 프로필
        client.post("/api/v1/speakers", json={"speaker_label": "SPEAKER_00", "display_name": "전역"})
        # 회의록 오버라이드
        client.post("/api/v1/speakers", json={
            "speaker_label": "SPEAKER_00",
            "display_name": "오버라이드",
            "task_id": seeded_db["task_id"],
        })
        # 다른 회의록
        client.post("/api/v1/speakers", json={
            "speaker_label": "SPEAKER_00",
            "display_name": "다른 회의록",
            "task_id": "other-task-999",
        })

        resp = client.get(f"/api/v1/speakers?task_id={seeded_db['task_id']}")

    assert resp.status_code == 200
    body = resp.json()
    names = {item["display_name"] for item in body["items"]}
    # 전역 + 해당 회의록만 포함
    assert "전역" in names
    assert "오버라이드" in names
    assert "다른 회의록" not in names


# ---------------------------------------------------------------------------
# 소유권 격리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ownership_isolation(db_engine, seeded_db):
    """다른 사용자의 화자 프로필은 404."""
    app_a = _make_app(db_engine, seeded_db["user_a"])
    app_b = _make_app(db_engine, seeded_db["user_b"])

    with TestClient(app_a) as client_a:
        create_resp = client_a.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "A의 화자"},
        )
    profile_id = create_resp.json()["id"]

    with TestClient(app_b) as client_b:
        resp = client_b.get(f"/api/v1/speakers/{profile_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 수정 (PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_speaker(db_engine, seeded_db):
    """화자 이름 수정."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "원래 이름"},
        )
        profile_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/speakers/{profile_id}",
            json={"display_name": "수정된 이름", "role": "개발자"},
        )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "수정된 이름"
    assert resp.json()["role"] == "개발자"


# ---------------------------------------------------------------------------
# 삭제 (DELETE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_speaker(db_engine, seeded_db):
    """화자 프로필 삭제 후 404."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "삭제 대상"},
        )
        profile_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/speakers/{profile_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/speakers/{profile_id}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# 단건 조회 (GET /api/v1/speakers/{speaker_id})
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_speaker_by_id(db_engine, seeded_db):
    """생성된 화자 프로필을 ID로 조회한다."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_01", "display_name": "조회 대상"},
        )
        assert create_resp.status_code == 201
        profile_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/v1/speakers/{profile_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["id"] == profile_id
        assert body["display_name"] == "조회 대상"
