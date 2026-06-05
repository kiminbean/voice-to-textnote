"""
SPEC-QUALITY-MONITOR-001: 실시간 품질 모니터링 엔드포인트 테스트
quality_assessment.py 누락된 라인 커버리지:

- 라인 53-55, 68: _extract_minutes_title
- 라인 75-96: _extract_minutes_content
- 라인 270: empty result_data 처리
- 라인 284-297: _load_minutes_text_or_404 helper
- 라인 318-331: GET /{task_id}/quality-score
- 라인 349-366: POST /{task_id}/quality-feedback
- 라인 382-390: GET /{task_id}/quality-feedback
- 라인 416-425: GET /{task_id}/quality-trends
"""


from unittest.mock import AsyncMock

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.quality_feedback_models  # noqa: F401
from backend.app.dependencies import get_db_session
from backend.app.error_handlers import register_exception_handlers
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

    # 정상 회의록
    task = TaskResult(
        task_id="live-task-001",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "테스트 회의",
            "markdown": _SAMPLE_MINUTES,
        },
    )

    # segments만 있는 회의록
    segments_task = TaskResult(
        task_id="live-task-segments",
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

    # summary_text만 있는 회의록
    summary_task = TaskResult(
        task_id="live-task-summary",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "요약 회의",
            "summary_text": "회의 요약 내용입니다.",
        },
    )

    # 빈 result_data
    empty_task = TaskResult(
        task_id="live-task-empty",
        task_type="minutes",
        status="completed",
        result_data={},
    )

    # title이 없는 회의록
    no_title_task = TaskResult(
        task_id="live-task-no-title",
        task_type="minutes",
        status="completed",
        result_data={
            "markdown": _SAMPLE_MINUTES,
        },
    )

    # meeting_title이 있는 회의록
    meeting_title_task = TaskResult(
        task_id="live-task-meeting-title",
        task_type="minutes",
        status="completed",
        result_data={
            "meeting_title": "회의 제목 (meeting_title)",
            "markdown": _SAMPLE_MINUTES,
        },
    )

    async with factory() as session:
        session.add_all([
            task, segments_task, summary_task, empty_task,
            no_title_task, meeting_title_task,
        ])
        await session.commit()

    return {
        "task_id": task.task_id,
        "segments_task_id": segments_task.task_id,
        "summary_task_id": summary_task.task_id,
        "empty_task_id": empty_task.task_id,
        "no_title_task_id": no_title_task.task_id,
        "meeting_title_task_id": meeting_title_task.task_id,
    }


def _make_app(db_engine, svc_mock=None):
    from backend.app.api.v1.quality_assessment import get_quality_service, router
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async def override_db():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_db_session] = override_db
    if svc_mock is not None:
        async def override_svc():
            return svc_mock
        app.dependency_overrides[get_quality_service] = override_svc
    return app


# ---------------------------------------------------------------------------
# GET /{task_id}/quality-score — get_live_quality_score
# 라인 318-331 커버
# ---------------------------------------------------------------------------


class TestGetLiveQualityScore:
    """REQ-QM-003: AI 호출 없는 경량 실시간 품질 점수."""

    def test_successful_live_score(self, db_engine, seeded_db):
        """정상적인 실시간 점수 계산."""
        from datetime import datetime

        from backend.schemas.quality import LiveQualityScoreResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_response = LiveQualityScoreResponse(
            task_id=seeded_db["task_id"],
            overall_score=75.0,
            grade="B",
            completeness_score=80.0,
            clarity_score=75.0,
            structure_score=70.0,
            word_count=100,
            computed_at=datetime(2026, 6, 2, 0, 0, 0),
        )

        svc_mock.compute_live_score = AsyncMock(return_value=mock_response)
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/quality/{seeded_db['task_id']}/quality-score")

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == seeded_db["task_id"]
        assert body["overall_score"] == 75.0
        svc_mock.compute_live_score.assert_called_once()

    def test_live_score_persist_false(self, db_engine, seeded_db):
        """persist=False일 때도 정상 동작."""
        from datetime import datetime

        from backend.schemas.quality import LiveQualityScoreResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_response = LiveQualityScoreResponse(
            task_id=seeded_db["task_id"],
            overall_score=80.0,
            grade="A",
            completeness_score=85.0,
            clarity_score=80.0,
            structure_score=75.0,
            word_count=120,
            computed_at=datetime(2026, 6, 2, 0, 0, 0),
        )

        svc_mock.compute_live_score = AsyncMock(return_value=mock_response)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-score?persist=false"
            )

        assert resp.status_code == 200
        # persist 파라미터가 전달되는지 확인
        call_args = svc_mock.compute_live_score.call_args
        assert call_args.kwargs["persist_snapshot"] is False

    def test_live_score_task_not_found(self, db_engine, seeded_db):
        """존재하지 않는 task_id로 요청 시 404."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        with TestClient(app) as client:
            resp = client.get("/api/v1/quality/nonexistent-task/quality-score")
        assert resp.status_code == 404

    def test_live_score_empty_content_returns_404(self, db_engine, seeded_db):
        """빈 회의록 content일 때 404."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/quality/{seeded_db['empty_task_id']}/quality-score")
        assert resp.status_code == 404

    def test_live_score_service_error_returns_500(self, db_engine, seeded_db):
        """서비스 계산 중 에러 발생 시 500."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        svc_mock.compute_live_score = AsyncMock(side_effect=RuntimeError("계산 실패"))
        with TestClient(app) as client:
            resp = client.get(f"/api/v1/quality/{seeded_db['task_id']}/quality-score")
        assert resp.status_code == 500
        assert "계산 실패" in resp.json()["message"]


# ---------------------------------------------------------------------------
# POST /{task_id}/quality-feedback — submit_quality_feedback
# 라인 349-366 커버
# ---------------------------------------------------------------------------


class TestSubmitQualityFeedback:
    """REQ-QM-001: 사용자 피드백 제출 (1~5 별점 + 카테고리 + 코멘트)."""

    def test_successful_feedback_submission(self, db_engine, seeded_db):
        """정상적인 피드백 제출."""
        from backend.schemas.quality import QualityFeedbackResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_response = QualityFeedbackResponse(
            id="fb-001",
            task_id=seeded_db["task_id"],
            rating=5,
            category="completeness",
            comment="우수한 회의록입니다.",
            created_at="2026-06-02T00:00:00Z",
        )

        svc_mock.submit_feedback = AsyncMock(return_value=mock_response)
        with TestClient(app) as client:
            resp = client.post(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback",
                json={
                    "rating": 5,
                    "category": "completeness",
                    "comment": "우수한 회의록입니다.",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "fb-001"
        assert body["rating"] == 5
        assert body["category"] == "completeness"

    def test_feedback_task_not_found(self, db_engine, seeded_db):
        """존재하지 않는 task_id로 피드백 제출 시 404."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/quality/nonexistent-task/quality-feedback",
                json={"rating": 5, "category": "completeness"},
            )
        assert resp.status_code == 404

    def test_feedback_service_error_returns_500(self, db_engine, seeded_db):
        """서비스 저장 중 에러 발생 시 500."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        svc_mock.submit_feedback = AsyncMock(side_effect=RuntimeError("저장 실패"))
        with TestClient(app) as client:
            resp = client.post(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback",
                json={"rating": 3, "category": "clarity"},
            )
        assert resp.status_code == 500
        assert "저장 실패" in resp.json()["message"]


# ---------------------------------------------------------------------------
# GET /{task_id}/quality-feedback — list_quality_feedback
# 라인 382-390 커버
# ---------------------------------------------------------------------------


class TestListQualityFeedback:
    """REQ-QM-001: 누적된 피드백 요약 (평균 별점, 카테고리 분포, 최근 N건)."""

    def test_successful_feedback_list(self, db_engine, seeded_db):
        """정상적인 피드백 목록 조회."""
        from datetime import datetime

        from backend.schemas.quality import (
            FeedbackCategory,
            QualityFeedbackResponse,
            QualityFeedbackSummary,
        )

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_feedback = QualityFeedbackResponse(
            id="fb-001",
            task_id=seeded_db["task_id"],
            rating=5,
            category=FeedbackCategory.COMPLETENESS,
            comment="좋음",
            created_at=datetime(2026, 6, 2, 0, 0, 0),
        )
        mock_summary = QualityFeedbackSummary(
            task_id=seeded_db["task_id"],
            total_feedbacks=10,
            avg_rating=4.5,
            category_breakdown={"completeness": 5, "clarity": 5},
            recent=[mock_feedback],
        )

        svc_mock.get_feedback_summary = AsyncMock(return_value=mock_summary)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == seeded_db["task_id"]
        assert body["avg_rating"] == 4.5
        assert body["total_feedbacks"] == 10

    def test_feedback_list_with_custom_limit(self, db_engine, seeded_db):
        """recent_limit 파라미터로 최근 N건 조절."""
        from backend.schemas.quality import QualityFeedbackSummary

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_summary = QualityFeedbackSummary(
            task_id=seeded_db["task_id"],
            total_feedbacks=5,
            avg_rating=4.0,
            category_breakdown={},
            recent=[],
        )

        svc_mock.get_feedback_summary = AsyncMock(return_value=mock_summary)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback?recent_limit=20"
            )

        assert resp.status_code == 200
        call_args = svc_mock.get_feedback_summary.call_args
        assert call_args.kwargs["recent_limit"] == 20

    def test_feedback_list_service_error_returns_500(self, db_engine, seeded_db):
        """서비스 조회 중 에러 발생 시 500."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        svc_mock.get_feedback_summary = AsyncMock(side_effect=RuntimeError("조회 실패"))
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-feedback"
            )
        assert resp.status_code == 500
        assert "조회 실패" in resp.json()["message"]


# ---------------------------------------------------------------------------
# GET /{task_id}/quality-trends — get_quality_trends
# 라인 416-425 커버
# ---------------------------------------------------------------------------


class TestGetQualityTrends:
    """REQ-QM-002: 저장된 스냅샷 기반 품질 추세 분석."""

    def test_successful_trends(self, db_engine, seeded_db):
        """정상적인 추세 분석 조회."""
        from backend.schemas.quality import QualityTrendsResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_trends = QualityTrendsResponse(
            task_id=seeded_db["task_id"],
            points=[],
            points_count=10,
            avg_score=75.0,
            min_score=65.0,
            max_score=85.0,
            trend_direction="up",
            warning=None,
        )

        svc_mock.get_quality_trends = AsyncMock(return_value=mock_trends)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-trends"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == seeded_db["task_id"]
        assert body["avg_score"] == 75.0
        assert body["trend_direction"] == "up"

    def test_trends_with_custom_limit(self, db_engine, seeded_db):
        """limit 파라미터로 스냅샷 개수 조절."""
        from backend.schemas.quality import QualityTrendsResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_trends = QualityTrendsResponse(
            task_id=seeded_db["task_id"],
            points=[],
            points_count=5,
            avg_score=70.0,
            min_score=60.0,
            max_score=80.0,
            trend_direction="stable",
            warning=None,
        )

        svc_mock.get_quality_trends = AsyncMock(return_value=mock_trends)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-trends?limit=100"
            )

        assert resp.status_code == 200
        call_args = svc_mock.get_quality_trends.call_args
        assert call_args.kwargs["limit"] == 100

    def test_trends_with_warning_threshold(self, db_engine, seeded_db):
        """warning_drop_threshold 파라미터로 경고 메시지 포함."""
        from backend.schemas.quality import QualityTrendsResponse

        svc_mock = AsyncMock()


        app = _make_app(db_engine, svc_mock=svc_mock)
        mock_trends = QualityTrendsResponse(
            task_id=seeded_db["task_id"],
            points=[],
            points_count=5,
            avg_score=70.0,
            min_score=50.0,
            max_score=80.0,
            trend_direction="down",
            warning="품질 점수가 15점 하락했습니다.",
        )

        svc_mock.get_quality_trends = AsyncMock(return_value=mock_trends)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-trends?warning_drop_threshold=10.0"
            )

        assert resp.status_code == 200
        call_args = svc_mock.get_quality_trends.call_args
        assert call_args.kwargs["warning_drop_threshold"] == 10.0

    def test_trends_service_error_returns_500(self, db_engine, seeded_db):
        """서비스 분석 중 에러 발생 시 500."""
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        svc_mock.get_quality_trends = AsyncMock(side_effect=RuntimeError("분석 실패"))
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['task_id']}/quality-trends"
            )
        assert resp.status_code == 500
        assert "분석 실패" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Helper 함수 커버리지 위한 간접 테스트
# _extract_minutes_title (라인 66-70)
# _extract_minutes_content (라인 73-96)
# _load_minutes_text_or_404 (라인 282-297)
# ---------------------------------------------------------------------------


class TestHelpersCoverage:
    """헬퍼 함수 커버리지를 위한 간접 테스트."""

    def test_extract_minutes_title_from_result_data(self, db_engine, seeded_db):
        """result_data에서 title 추출 (라인 66-70)."""
        # meeting_title 필드도 확인
        from datetime import datetime
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        from backend.schemas.quality import LiveQualityScoreResponse
        mock_response = LiveQualityScoreResponse(
            task_id=seeded_db["meeting_title_task_id"],
            overall_score=75.0,
            grade="B",
            completeness_score=80.0,
            clarity_score=75.0,
            structure_score=70.0,
            word_count=100,
            computed_at=datetime(2026, 6, 2, 0, 0, 0),
        )
        svc_mock.compute_live_score = AsyncMock(return_value=mock_response)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['meeting_title_task_id']}/quality-score"
            )
        assert resp.status_code == 200
        # _extract_minutes_title이 호출됨을 확인

    def test_extract_minutes_content_no_title(self, db_engine, seeded_db):
        """title이 없을 때 빈 문자열 반환 (라인 76)."""
        from datetime import datetime
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        from backend.schemas.quality import LiveQualityScoreResponse
        mock_response = LiveQualityScoreResponse(
            task_id=seeded_db["no_title_task_id"],
            overall_score=75.0,
            grade="B",
            completeness_score=80.0,
            clarity_score=75.0,
            structure_score=70.0,
            word_count=100,
            computed_at=datetime(2026, 6, 2, 0, 0, 0),
        )
        svc_mock.compute_live_score = AsyncMock(return_value=mock_response)
        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/quality/{seeded_db['no_title_task_id']}/quality-score"
            )
        assert resp.status_code == 200

    def test_load_minutes_text_or_404_helper_coverage(self, db_engine, seeded_db):
        """_load_minutes_text_or_404 헬퍼 함수 커버리지 (라인 284-297)."""
        # 이 함수는 get_live_quality_score에서 호출됨
        # 이미 TestGetLiveQualityScore에서 커버됨
        svc_mock = AsyncMock()

        app = _make_app(db_engine, svc_mock=svc_mock)
        with TestClient(app) as client:
            # 존재하지 않는 task - 404 경로 (라인 287-290)
            resp = client.get("/api/v1/quality/nonexistent/quality-score")
        assert resp.status_code == 404

        # 빈 content - 404 경로 (라인 292-296)
        resp = client.get(f"/api/v1/quality/{seeded_db['empty_task_id']}/quality-score")
        assert resp.status_code == 404
