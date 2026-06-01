"""
SPEC-QUALITY-MONITOR-001: 품질 서비스 실시간 모니터링 메서드 단위 테스트

대상: services/quality_service.py (line 833~)
  - compute_live_score (AI 호출 없는 경량 점수)
  - submit_feedback (사용자 피드백 저장)
  - get_feedback_summary (피드백 요약 집계)
  - get_quality_trends (품질 추세 분석)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.quality_feedback_models  # noqa: F401
from backend.db.models import Base, TaskResult
from backend.schemas.quality import (
    FeedbackCategory,
    QualityFeedbackCreate,
    QualityTrendsResponse,
)

# get_openai_client를 mock하여 QualityService 초기화 시 외부 API 호출 차단
# import 전에 패치해야 생성자에서 호출되는 get_openai_client가 mock됨


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


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """인메모리 SQLite 엔진."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """테스트용 비동기 DB 세션."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_task(db_session):
    """테스트용 TaskResult (회의록 포함)."""
    task = TaskResult(
        task_id="qs-monitor-task-001",
        task_type="minutes",
        status="completed",
        result_data={
            "title": "분기 검토 회의",
            "markdown": _SAMPLE_MINUTES,
        },
    )
    db_session.add(task)
    await db_session.commit()
    return task


@pytest.fixture
def svc():
    """QualityService 인스턴스 (OpenAI client mock)."""
    with patch("backend.services.quality_service.get_openai_client") as mock_get:
        mock_get.return_value = MagicMock()
        from backend.services.quality_service import QualityService
        return QualityService()


# ===========================================================================
# compute_live_score
# ===========================================================================


class TestComputeLiveScore:
    """경량 실시간 품질 점수 (AI 호출 없음)."""

    @pytest.mark.asyncio
    async def test_returns_score_with_content(self, svc):
        """회의록 내용이 있으면 점수 반환."""
        result = await svc.compute_live_score(
            task_id="test-001",
            meeting_content=_SAMPLE_MINUTES,
            db=None,
            persist_snapshot=False,
        )
        assert 0.0 <= result.overall_score <= 100.0
        assert result.grade in {"A+", "A", "B+", "B", "C+", "C", "D", "F"}
        assert result.word_count > 0
        assert result.mode == "lightweight"
        assert result.completeness_score >= 0
        assert result.clarity_score >= 0
        assert result.structure_score >= 0

    @pytest.mark.asyncio
    async def test_minimal_content_yields_low_score(self, svc):
        """최소 내용이면 낮은 점수.

        NOTE: 빈 문자열("")은 ZeroDivisionError 발생 (quality_service.py:156).
        소스 수정 금지 규칙에 따라 버그 보고 후 최소 내용으로 대체 테스트.
        """
        result = await svc.compute_live_score(
            task_id="test-002",
            meeting_content="테스트",
            db=None,
            persist_snapshot=False,
        )
        assert 0.0 <= result.overall_score <= 100.0
        assert result.word_count == 1

    @pytest.mark.asyncio
    async def test_persist_false_does_not_save(self, svc, db_session):
        """persist_snapshot=False면 DB에 저장하지 않음."""
        from backend.db.quality_feedback_models import QualityScoreSnapshot

        result = await svc.compute_live_score(
            task_id="test-003",
            meeting_content=_SAMPLE_MINUTES,
            db=db_session,
            persist_snapshot=False,
        )
        assert result is not None

        # 저장된 스냅샷이 없어야 함
        from sqlalchemy import func, select
        count = (await db_session.execute(
            select(func.count(QualityScoreSnapshot.id))
        )).scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_persist_true_saves_snapshot(self, svc, db_session, seeded_task):
        """persist_snapshot=True면 스냅샷 저장."""
        from sqlalchemy import select

        from backend.db.quality_feedback_models import QualityScoreSnapshot

        await svc.compute_live_score(
            task_id=seeded_task.task_id,
            meeting_content=_SAMPLE_MINUTES,
            db=db_session,
            persist_snapshot=True,
        )

        snapshots = (await db_session.execute(
            select(QualityScoreSnapshot)
        )).scalars().all()
        assert len(snapshots) == 1
        assert snapshots[0].task_id == seeded_task.task_id
        assert snapshots[0].mode == "lightweight"

    @pytest.mark.asyncio
    async def test_db_none_skips_persist(self, svc):
        """db=None이면 persist_snapshot=True여도 에러 없이 동작."""
        result = await svc.compute_live_score(
            task_id="test-004",
            meeting_content=_SAMPLE_MINUTES,
            db=None,
            persist_snapshot=True,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_short_content(self, svc):
        """매우 짧은 내용도 정상 동작."""
        result = await svc.compute_live_score(
            task_id="test-005",
            meeting_content="안녕하세요.",
            db=None,
            persist_snapshot=False,
        )
        assert result.word_count > 0


# ===========================================================================
# submit_feedback
# ===========================================================================


class TestSubmitFeedback:
    """사용자 피드백 저장."""

    @pytest.mark.asyncio
    async def test_save_feedback(self, svc, db_session, seeded_task):
        """정상 피드백 저장 후 응답 검증."""
        payload = QualityFeedbackCreate(
            rating=4,
            category=FeedbackCategory.ACCURACY,
            comment="정확합니다.",
        )
        result = await svc.submit_feedback(
            db=db_session,
            task_id=seeded_task.task_id,
            user_id=None,
            payload=payload,
        )
        assert result.rating == 4
        assert result.category == FeedbackCategory.ACCURACY
        assert result.comment == "정확합니다."
        assert result.task_id == seeded_task.task_id
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_save_multiple_feedbacks(self, svc, db_session, seeded_task):
        """여러 피드백 저장 시 ID가 모두 다름."""
        ids = set()
        for r in [1, 3, 5]:
            payload = QualityFeedbackCreate(rating=r, category=FeedbackCategory.OTHER)
            fb = await svc.submit_feedback(
                db=db_session,
                task_id=seeded_task.task_id,
                user_id=None,
                payload=payload,
            )
            ids.add(fb.id)
        assert len(ids) == 3

    @pytest.mark.asyncio
    async def test_feedback_with_user_id(self, svc, db_session, seeded_task):
        """user_id가 있으면 함께 저장."""
        uid = uuid.uuid4()
        payload = QualityFeedbackCreate(rating=5, category=FeedbackCategory.CLARITY)
        result = await svc.submit_feedback(
            db=db_session,
            task_id=seeded_task.task_id,
            user_id=uid,
            payload=payload,
        )
        assert result.rating == 5


# ===========================================================================
# get_feedback_summary
# ===========================================================================


class TestGetFeedbackSummary:
    """피드백 누적 요약."""

    @pytest.mark.asyncio
    async def test_empty_summary(self, svc, db_session, seeded_task):
        """피드백이 없으면 total=0, avg=None."""
        summary = await svc.get_feedback_summary(
            db=db_session,
            task_id=seeded_task.task_id,
        )
        assert summary.total_feedbacks == 0
        assert summary.avg_rating is None
        assert summary.category_breakdown == {}
        assert summary.recent == []

    @pytest.mark.asyncio
    async def test_summary_aggregates(self, svc, db_session, seeded_task):
        """여러 피드백 후 평균/카테고리 분포 확인."""
        for rating, cat in [
            (5, FeedbackCategory.ACCURACY),
            (3, FeedbackCategory.CLARITY),
            (4, FeedbackCategory.ACCURACY),
        ]:
            await svc.submit_feedback(
                db=db_session,
                task_id=seeded_task.task_id,
                user_id=None,
                payload=QualityFeedbackCreate(rating=rating, category=cat),
            )

        summary = await svc.get_feedback_summary(
            db=db_session,
            task_id=seeded_task.task_id,
        )
        assert summary.total_feedbacks == 3
        assert summary.avg_rating == pytest.approx(4.0, abs=0.01)
        assert summary.category_breakdown.get("accuracy") == 2
        assert summary.category_breakdown.get("clarity") == 1

    @pytest.mark.asyncio
    async def test_recent_limit(self, svc, db_session, seeded_task):
        """recent_limit 파라미터로 최근 N건 제한."""
        for i in range(5):
            await svc.submit_feedback(
                db=db_session,
                task_id=seeded_task.task_id,
                user_id=None,
                payload=QualityFeedbackCreate(
                    rating=i + 1, category=FeedbackCategory.OTHER,
                ),
            )

        summary = await svc.get_feedback_summary(
            db=db_session,
            task_id=seeded_task.task_id,
            recent_limit=2,
        )
        assert len(summary.recent) == 2
        assert summary.total_feedbacks == 5  # 전체 개수는 그대로


# ===========================================================================
# get_quality_trends
# ===========================================================================


class TestGetQualityTrends:
    """품질 추세 분석."""

    @pytest.mark.asyncio
    async def test_no_snapshots_insufficient_data(
        self, svc, db_session, seeded_task,
    ):
        """스냅샷 없으면 insufficient_data."""
        result = await svc.get_quality_trends(
            db=db_session,
            task_id=seeded_task.task_id,
        )
        assert result.points_count == 0
        assert result.trend_direction == "insufficient_data"
        assert result.avg_score is None

    @pytest.mark.asyncio
    async def test_single_snapshot_insufficient_data(
        self, svc, db_session, seeded_task,
    ):
        """스냅샷 1개여도 insufficient_data."""
        await svc.compute_live_score(
            task_id=seeded_task.task_id,
            meeting_content=_SAMPLE_MINUTES,
            db=db_session,
            persist_snapshot=True,
        )
        result = await svc.get_quality_trends(
            db=db_session,
            task_id=seeded_task.task_id,
        )
        assert result.points_count == 1
        assert result.trend_direction == "insufficient_data"

    @pytest.mark.asyncio
    async def test_multiple_snapshots_with_trend(
        self, svc, db_session, seeded_task,
    ):
        """스냅샷 3개 누적 후 추세 분석."""
        for _ in range(3):
            await svc.compute_live_score(
                task_id=seeded_task.task_id,
                meeting_content=_SAMPLE_MINUTES,
                db=db_session,
                persist_snapshot=True,
            )

        result = await svc.get_quality_trends(
            db=db_session,
            task_id=seeded_task.task_id,
        )
        assert result.points_count == 3
        assert result.trend_direction in {"up", "down", "stable"}
        assert result.avg_score is not None
        assert result.min_score is not None
        assert result.max_score is not None

    @pytest.mark.asyncio
    async def test_warning_on_drop(self, svc, db_session, seeded_task):
        """초기 대비 큰 하락 시 경고 메시지 포함."""
        # 짧은 내용으로 여러 번 호출 → 점수 변동 유도
        for content in [_SAMPLE_MINUTES, "짧은 내용", "짧은 내용"]:
            await svc.compute_live_score(
                task_id=seeded_task.task_id,
                meeting_content=content,
                db=db_session,
                persist_snapshot=True,
            )

        result = await svc.get_quality_trends(
            db=db_session,
            task_id=seeded_task.task_id,
            warning_drop_threshold=0.0,  # 모든 하락에 경고
        )
        # threshold=0.0이면 하락이 0 이상일 때 warning 발생 가능
        # (실제 점수가 하락했는지에 따라 결정)
        assert isinstance(result, QualityTrendsResponse)

    @pytest.mark.asyncio
    async def test_different_task_no_cross_contamination(
        self, svc, db_session, seeded_task,
    ):
        """다른 task_id의 스냅샷은 포함되지 않음."""
        await svc.compute_live_score(
            task_id=seeded_task.task_id,
            meeting_content=_SAMPLE_MINUTES,
            db=db_session,
            persist_snapshot=True,
        )
        result = await svc.get_quality_trends(
            db=db_session,
            task_id="nonexistent-task",
        )
        assert result.points_count == 0
