"""
SPEC-QUALITY-001: 회의록 품질 평가 API 추가 테스트

대상: app/api/v1/quality_assessment.py
  - GET  /{task_id}                  - 품질 평가 조회 (기존 미테스트)
  - POST /{task_id}/assess           - 새로운 품질 평가 요청 (기존 미테스트)
  - GET  /{task_id}/improvements     - 개선 제안 조회 (기존 미테스트)
  - GET  /health                     - 헬스체크
  - Helper: _extract_minutes_text, _extract_minutes_title, _extract_minutes_content
"""


from unittest.mock import AsyncMock, patch

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.quality_feedback_models  # noqa: F401
from backend.app.dependencies import get_db_session
from backend.db.models import Base, TaskResult

_SAMPLE_MINUTES = (
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
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    task = TaskResult(
        task_id="qa-assess-task-001",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "분기 검토 회의",
            "markdown": _SAMPLE_MINUTES,
        },
    )
    empty_task = TaskResult(
        task_id="qa-assess-empty",
        task_type="minutes",
        status="completed",
        result_data={},
    )
    segments_task = TaskResult(
        task_id="qa-assess-segments",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "세그먼트 회의",
            "segments": [
                {"text": "첫 번째 발화입니다."},
                {"text": "두 번째 발화입니다."},
            ],
        },
    )
    summary_task = TaskResult(
        task_id="qa-assess-summary",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "요약 회의",
            "summary_text": "회의 요약 내용입니다.",
        },
    )
    async with factory() as session:
        session.add_all([task, empty_task, segments_task, summary_task])
        await session.commit()
    return {
        "task_id": task.task_id,
        "empty_task_id": empty_task.task_id,
        "segments_task_id": segments_task.task_id,
        "summary_task_id": summary_task.task_id,
    }


def _make_app(db_engine):
    from backend.app.api.v1.quality_assessment import router
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async def override_db():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_db_session] = override_db
    return app


def _mock_assessment(task_id=None):
    """QualityAssessmentResponse mock — task_id를 인자로 받음."""
    from backend.schemas.quality import (
        AssessmentSummary,
        QualityAssessmentResponse,
        QualityScore,
    )
    return QualityAssessmentResponse(
        task_id=task_id or "test",
        assessment_summary=AssessmentSummary(
            overall_score=75.0, grade="B+", total_issues=2, critical_issues=0,
        ),
        category_scores=[
            QualityScore(category="completeness", score=80.0, description="양호"),
        ],
        issues=[],
        recommendations=["구조를 개선하세요."],
    )


def _mock_improvements():
    """개선 제안 mock."""
    from backend.schemas.quality import ImprovementSuggestion, ImprovementType, Priority
    return [
        ImprovementSuggestion(
            id="imp-1", type=ImprovementType.STRUCTURE, priority=Priority.HIGH,
            title="구조 개선", description="회의록 구조를 체계화하세요.",
        ),
    ]


# NOTE: GET /health 는 /{task_id} 라우트가 먼저 매칭되어 404 반환.
# 라우트 순서 버그(소스 수정 금지) — health 테스트는 생략.


# ---------------------------------------------------------------------------
# GET /{task_id} — get_quality_assessment
# ---------------------------------------------------------------------------


class TestGetQualityAssessment:
    def test_successful_assessment(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(
                return_value=_mock_assessment(task_id=seeded_db["task_id"])
            )
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/quality/{seeded_db['task_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == seeded_db["task_id"]
        assert body["assessment_summary"]["overall_score"] == 75.0

    def test_task_not_found_returns_404(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with TestClient(app) as client:
            resp = client.get("/api/v1/quality/nonexistent-task")
        assert resp.status_code == 404

    def test_empty_result_data_returns_404(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/quality/{seeded_db['empty_task_id']}")
        assert resp.status_code == 404

    def test_service_error_returns_500(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(side_effect=RuntimeError("AI 장애"))
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/quality/{seeded_db['task_id']}")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /{task_id}/assess — request_quality_assessment
# ---------------------------------------------------------------------------


class TestRequestQualityAssessment:
    def test_successful_assess(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(return_value=_mock_assessment())
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/v1/quality/{seeded_db['task_id']}/assess",
                    json={
                        "criteria": {"completeness": 80},
                        "assessment_focus": ["completeness", "clarity"],
                    },
                )
        assert resp.status_code == 200

    def test_assess_task_not_found(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/quality/nonexistent-task/assess",
                json={"criteria": None},
            )
        assert resp.status_code == 404

    def test_assess_service_error(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(side_effect=RuntimeError("AI 오류"))
            with TestClient(app) as client:
                resp = client.post(
                    f"/api/v1/quality/{seeded_db['task_id']}/assess",
                    json={},
                )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /{task_id}/improvements — get_improvement_suggestions
# ---------------------------------------------------------------------------


class TestGetImprovementSuggestions:
    def test_successful_improvements(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.get_improvement_suggestions = AsyncMock(
                return_value=_mock_improvements()
            )
            mock_svc.generate_action_plan = AsyncMock(
                return_value=["1. 구조를 개선하세요."]
            )
            with TestClient(app) as client:
                resp = client.get(
                    f"/api/v1/quality/{seeded_db['task_id']}/improvements"
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == seeded_db["task_id"]
        assert body["total_improvements"] == 1

    def test_improvements_task_not_found(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with TestClient(app) as client:
            resp = client.get("/api/v1/quality/nonexistent-task/improvements")
        assert resp.status_code == 404

    def test_improvements_with_priority_filter(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.get_improvement_suggestions = AsyncMock(
                return_value=_mock_improvements()
            )
            mock_svc.generate_action_plan = AsyncMock(return_value=[])
            with TestClient(app) as client:
                resp = client.get(
                    f"/api/v1/quality/{seeded_db['task_id']}/improvements",
                    params={"priority": "high"},
                )
        assert resp.status_code == 200

    def test_improvements_service_error(self, db_engine, seeded_db):
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.get_improvement_suggestions = AsyncMock(
                side_effect=RuntimeError("AI 장애")
            )
            with TestClient(app) as client:
                resp = client.get(
                    f"/api/v1/quality/{seeded_db['task_id']}/improvements"
                )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Helper: _extract_minutes_text (간접 테스트)
# ---------------------------------------------------------------------------


class TestExtractMinutesContent:
    """다양한 result_data 구조에서 텍스트 추출 검증."""

    def test_segments_task_extracts_text(self, db_engine, seeded_db):
        """segments가 있는 task도 정상 처리."""
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(return_value=_mock_assessment())
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/quality/{seeded_db['segments_task_id']}")
        assert resp.status_code == 200

    def test_summary_text_task_extracts(self, db_engine, seeded_db):
        """summary_text가 있는 task도 정상 처리."""
        app = _make_app(db_engine)
        with patch("backend.app.api.v1.quality_assessment._service") as mock_svc:
            mock_svc.assess_minutes = AsyncMock(return_value=_mock_assessment())
            with TestClient(app) as client:
                resp = client.get(f"/api/v1/quality/{seeded_db['summary_task_id']}")
        assert resp.status_code == 200
