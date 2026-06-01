"""
SPEC-QUALITY-MONITOR-001: 실시간 품질 모니터링 / 피드백 / 추세 API 테스트
"""


import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.quality_feedback_models  # noqa: F401
from backend.db.models import Base, TaskResult

_SAMPLE_MINUTES_TEXT = (
    "## 회의 개요\n"
    "참석자: 김철수, 이영희\n"
    "일시: 2026년 5월 25일 오후 2시\n\n"
    "## 안건\n"
    "1. 분기 매출 검토\n"
    "2. 신규 제품 출시 계획\n\n"
    "## 의사결정\n"
    "- 신규 제품 출시일은 6월 15일로 확정\n"
    "- 마케팅 예산을 20% 증액하기로 합의\n\n"
    "## 액션 아이템\n"
    "- 김철수: 마케팅 자료 작성 (마감 6월 1일)\n"
    "- 이영희: 제품 사양서 최종 검토 (마감 5월 30일)\n"
)


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    task = TaskResult(
        task_id="quality-task-001",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "분기 검토 회의",
            "markdown": _SAMPLE_MINUTES_TEXT,
        },
    )
    empty_task = TaskResult(
        task_id="quality-task-empty",
        task_type="minutes",
        status="completed",
        result_data={},
    )

    async with session_factory() as session:
        session.add_all([task, empty_task])
        await session.commit()

    return {"task_id": task.task_id, "empty_task_id": empty_task.task_id}


def _make_app(db_engine) -> FastAPI:
    from backend.app.api.v1.quality_assessment import router
    from backend.app.dependencies import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return app


# ---------------------------------------------------------------------------
# GET /quality-score (실시간 경량 점수)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_quality_score_returns_scores(db_engine, seeded_db):
    """경량 점수 응답이 모든 필드를 포함."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.get(f"/api/v1/quality/{seeded_db['task_id']}/quality-score")

    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == seeded_db["task_id"]
    assert 0.0 <= body["overall_score"] <= 100.0
    assert body["grade"] in {"A+", "A", "B+", "B", "C+", "C", "D", "F"}
    assert body["word_count"] > 0
    assert body["mode"] == "lightweight"


@pytest.mark.asyncio
async def test_live_quality_score_404_when_no_minutes(db_engine, seeded_db):
    """빈 회의록은 404."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.get(
            f"/api/v1/quality/{seeded_db['empty_task_id']}/quality-score"
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_live_quality_score_404_when_task_missing(db_engine):
    """존재하지 않는 task_id는 404."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.get("/api/v1/quality/non-existent-task/quality-score")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /quality-feedback (피드백 제출)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_quality_feedback_success(db_engine, seeded_db):
    """피드백 제출 후 응답 형식 확인."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback",
            json={
                "rating": 4,
                "category": "accuracy",
                "comment": "전반적으로 정확합니다.",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == 4
    assert body["category"] == "accuracy"
    assert body["comment"] == "전반적으로 정확합니다."


@pytest.mark.asyncio
async def test_submit_quality_feedback_validation(db_engine, seeded_db):
    """별점 범위 밖은 422."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback",
            json={"rating": 0, "category": "other"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_quality_feedback_task_not_found(db_engine):
    """존재하지 않는 task_id는 404."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/quality/missing-task/quality-feedback",
            json={"rating": 3, "category": "other"},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /quality-feedback (요약 조회)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_summary_aggregates(db_engine, seeded_db):
    """피드백 누적 후 평균/카테고리 분포 확인."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        for rating, cat in [(5, "accuracy"), (3, "clarity"), (4, "accuracy")]:
            client.post(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback",
                json={"rating": rating, "category": cat},
            )

        resp = client.get(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_feedbacks"] == 3
    assert body["avg_rating"] == pytest.approx(4.0, abs=0.01)
    assert body["category_breakdown"].get("accuracy") == 2
    assert body["category_breakdown"].get("clarity") == 1
    assert len(body["recent"]) == 3


# ---------------------------------------------------------------------------
# GET /quality-trends (추세 분석)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trends_insufficient_data(db_engine, seeded_db):
    """스냅샷 없을 때 insufficient_data."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        resp = client.get(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-trends"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["points_count"] == 0
    assert body["trend_direction"] == "insufficient_data"


@pytest.mark.asyncio
async def test_trends_with_snapshots(db_engine, seeded_db):
    """quality-score 호출로 스냅샷 누적 후 trends 분석."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        # 여러 번 호출해 스냅샷 누적
        for _ in range(3):
            r = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-score?persist=true"
            )
            assert r.status_code == 200

        resp = client.get(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-trends"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["points_count"] == 3
    assert body["trend_direction"] in {"up", "down", "stable"}
    assert body["avg_score"] is not None
    assert body["min_score"] is not None
    assert body["max_score"] is not None


@pytest.mark.asyncio
async def test_score_persist_false_does_not_create_snapshot(db_engine, seeded_db):
    """persist=false 시 스냅샷 미생성 → trends는 여전히 비어있음."""
    app = _make_app(db_engine)
    with TestClient(app) as client:
        client.get(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-score?persist=false"
        )
        resp = client.get(
            f"/api/v1/quality/{seeded_db['task_id']}/quality-trends"
        )

    body = resp.json()
    assert body["points_count"] == 0
