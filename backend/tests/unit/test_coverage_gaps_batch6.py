"""커버리지 gap 보충 배치6: quality_assessment routes, export helpers, minutes/keywords"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/audio/quality_assessment.py — lines 123-145, 170, 176-185, 189-191, 217-236, 314
# ═══════════════════════════════════════════════════════════════════
class TestQualityAssessmentRoutes:
    @pytest.mark.asyncio
    async def test_get_quality_assessment_success(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_assessment
        task = MagicMock()
        task.result_data = {"text": "회의 내용", "title": "테스트"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.assess_minutes.return_value = MagicMock(task_id="t1", overall_score=85.0)

        result = await get_quality_assessment(
            task_id="t1", include_details=True, db=db, svc=svc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_quality_assessment_not_found(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_assessment
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        svc = AsyncMock()

        with pytest.raises(NotFoundError):
            await get_quality_assessment(task_id="missing", include_details=False, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_get_quality_assessment_no_content(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_assessment
        from backend.app.exceptions import NotFoundError
        task = MagicMock()
        task.result_data = {}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()

        with pytest.raises(NotFoundError):
            await get_quality_assessment(task_id="t1", include_details=False, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_get_quality_assessment_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_assessment
        from backend.app.exceptions import InternalServerError
        task = MagicMock()
        task.result_data = {"text": "회의 내용입니다"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.assess_minutes.side_effect = RuntimeError("boom")

        with pytest.raises(InternalServerError):
            await get_quality_assessment(task_id="t1", include_details=True, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_request_quality_assessment_success(self):
        from backend.app.api.v1.audio.quality_assessment import request_quality_assessment
        task = MagicMock()
        task.result_data = {"text": "회의 내용", "title": "테스트"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.assess_minutes.return_value = MagicMock(task_id="t1", overall_score=90.0)
        payload = MagicMock()
        payload.criteria = None
        payload.assessment_focus = None

        result = await request_quality_assessment(
            task_id="t1", payload=payload, db=db, svc=svc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_request_quality_assessment_not_found(self):
        from backend.app.api.v1.audio.quality_assessment import request_quality_assessment
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        svc = AsyncMock()
        payload = MagicMock()

        with pytest.raises(NotFoundError):
            await request_quality_assessment(task_id="missing", payload=payload, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_request_quality_assessment_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import request_quality_assessment
        from backend.app.exceptions import InternalServerError
        task = MagicMock()
        task.result_data = {"text": "회의 내용입니다"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.assess_minutes.side_effect = RuntimeError("fail")
        payload = MagicMock()
        payload.criteria = None
        payload.assessment_focus = None

        with pytest.raises(InternalServerError):
            await request_quality_assessment(task_id="t1", payload=payload, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_get_improvement_suggestions_success(self):
        from backend.app.api.v1.audio.quality_assessment import get_improvement_suggestions
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_improvement_suggestions = AsyncMock(return_value=[])
        svc.generate_action_plan = AsyncMock(return_value=[])

        result = await get_improvement_suggestions(
            task_id="t1", improvement_type="all", priority="high", db=db, svc=svc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_improvement_suggestions_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import get_improvement_suggestions
        from backend.app.exceptions import InternalServerError
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_improvement_suggestions = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(InternalServerError):
            await get_improvement_suggestions(
                task_id="t1", improvement_type="all", priority="high", db=db, svc=svc,
            )

    @pytest.mark.asyncio
    async def test_get_live_quality_score_success(self):
        from backend.app.api.v1.audio.quality_assessment import get_live_quality_score
        task = MagicMock()
        task.result_data = {"text": "회의 내용입니다"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.compute_live_score = AsyncMock(return_value=MagicMock(task_id="t1", score=75.0))

        result = await get_live_quality_score(
            task_id="t1", persist=True, db=db, svc=svc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_live_quality_score_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import get_live_quality_score
        from backend.app.exceptions import InternalServerError
        task = MagicMock()
        task.result_data = {"text": "회의 내용입니다"}
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.compute_live_score = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(InternalServerError):
            await get_live_quality_score(task_id="t1", persist=True, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_submit_quality_feedback_not_found(self):
        from backend.app.api.v1.audio.quality_assessment import submit_quality_feedback
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        svc = AsyncMock()
        payload = MagicMock()

        with pytest.raises(NotFoundError):
            await submit_quality_feedback(task_id="missing", payload=payload, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_submit_quality_feedback_success(self):
        from backend.app.api.v1.audio.quality_assessment import submit_quality_feedback
        task = MagicMock()
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.submit_feedback = AsyncMock(return_value=MagicMock(task_id="t1", rating=5))
        payload = MagicMock()

        result = await submit_quality_feedback(task_id="t1", payload=payload, db=db, svc=svc)
        assert result is not None

    @pytest.mark.asyncio
    async def test_submit_quality_feedback_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import submit_quality_feedback
        from backend.app.exceptions import InternalServerError
        task = MagicMock()
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
        svc = AsyncMock()
        svc.submit_feedback = AsyncMock(side_effect=RuntimeError("fail"))
        payload = MagicMock()

        with pytest.raises(InternalServerError):
            await submit_quality_feedback(task_id="t1", payload=payload, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_list_quality_feedback_success(self):
        from backend.app.api.v1.audio.quality_assessment import list_quality_feedback
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_feedback_summary = AsyncMock(return_value=MagicMock(task_id="t1", average_rating=4.5))

        result = await list_quality_feedback(task_id="t1", recent_limit=10, db=db, svc=svc)
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_quality_feedback_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import list_quality_feedback
        from backend.app.exceptions import InternalServerError
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_feedback_summary = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(InternalServerError):
            await list_quality_feedback(task_id="t1", recent_limit=10, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_get_quality_trends_success(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_trends
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_quality_trends = AsyncMock(return_value=MagicMock(task_id="t1", direction="stable"))

        result = await get_quality_trends(
            task_id="t1", limit=50, warning_drop_threshold=None, db=db, svc=svc,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_quality_trends_unexpected_error(self):
        from backend.app.api.v1.audio.quality_assessment import get_quality_trends
        from backend.app.exceptions import InternalServerError
        db = AsyncMock()
        svc = AsyncMock()
        svc.get_quality_trends = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(InternalServerError):
            await get_quality_trends(
                task_id="t1", limit=50, warning_drop_threshold=None, db=db, svc=svc,
            )


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/analytics/export.py — lines 27, 93, 96
# ═══════════════════════════════════════════════════════════════════
class TestExportServiceFactory:
    def test_get_export_service(self):
        from backend.app.api.v1.analytics.export import get_export_service
        from backend.services.export_service import ExportService
        result = get_export_service()
        assert isinstance(result, ExportService)

    @pytest.mark.asyncio
    async def test_export_batch_empty_ids(self):
        from backend.app.api.v1.analytics.export import export_batch_meetings
        from backend.app.exceptions import UnprocessableEntityError
        db = AsyncMock()
        svc = MagicMock()
        req = MagicMock()
        req.task_ids = []
        req.format = "pdf"
        req.filters = None

        with pytest.raises(UnprocessableEntityError):
            await export_batch_meetings(request=req, db=db, svc=svc)

    @pytest.mark.asyncio
    async def test_export_batch_too_many(self):
        from backend.app.api.v1.analytics.export import export_batch_meetings
        from backend.app.exceptions import UnprocessableEntityError
        db = AsyncMock()
        svc = MagicMock()
        req = MagicMock()
        req.task_ids = [f"t{i}" for i in range(51)]
        req.format = "pdf"
        req.filters = None

        with pytest.raises(UnprocessableEntityError):
            await export_batch_meetings(request=req, db=db, svc=svc)


# ═══════════════════════════════════════════════════════════════════
# app/api/v1/minutes/keywords.py — lines 27, 40 (factory + extract route)
# ═══════════════════════════════════════════════════════════════════
class TestMinutesKeywordsFactory:
    def test_get_keyword_service(self):
        from backend.app.api.v1.minutes.keywords import get_keyword_service
        from backend.services.keyword_service import KeywordService
        result = get_keyword_service()
        assert isinstance(result, KeywordService)

    @pytest.mark.asyncio
    async def test_extract_keywords_route_call(self):
        from backend.app.api.v1.minutes.keywords import extract_keywords
        svc = MagicMock()
        svc.extract_from_text.return_value = MagicMock(
            keywords=[{"keyword": "테스트", "score": 0.9}], total=1,
        )
        payload = MagicMock()
        payload.text = "회의 테스트 내용"
        payload.language = "ko"
        payload.max_keywords = 10
        payload.min_score = 0.0

        result = await extract_keywords(payload=payload, svc=svc)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════
# services/keyword_service.py — lines 184, 195-196 (search loop branches)
# search_keywords(session, keywords, filter, page, page_size, sort)
# ═══════════════════════════════════════════════════════════════════
class TestKeywordServiceSearchBranches:
    @pytest.mark.asyncio
    async def test_search_with_empty_db_results(self):
        from backend.services.keyword_service import KeywordService
        from backend.schemas.keyword import KeywordSearchFilter, SortOption
        svc = KeywordService()
        session = MagicMock()
        query_builder = MagicMock()
        query_builder.filter.return_value = query_builder
        query_builder.order_by.return_value = MagicMock()
        session.query.return_value = query_builder
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ))

        results = await svc.search_keywords(
            session=session,
            keywords=["존재하지않는키워드"],
            filter=KeywordSearchFilter(),
            page=1,
            page_size=20,
            sort=SortOption.relevance,
        )
        assert results.total_hits == 0

    @pytest.mark.asyncio
    async def test_search_with_no_content_result(self):
        """result_data가 빈 dict인 결과는 content 추출 실패 → continue 분기"""
        from backend.services.keyword_service import KeywordService
        from backend.schemas.keyword import KeywordSearchFilter, SortOption
        svc = KeywordService()
        session = MagicMock()
        task_result = MagicMock()
        task_result.result_data = {}
        task_result.task_id = "t1"
        query_builder = MagicMock()
        query_builder.filter.return_value = query_builder
        query_builder.order_by.return_value = MagicMock()
        session.query.return_value = query_builder
        session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[task_result])))
        ))

        results = await svc.search_keywords(
            session=session,
            keywords=["테스트"],
            filter=KeywordSearchFilter(),
            page=1,
            page_size=20,
            sort=SortOption.relevance,
        )
        assert results.total_hits == 0


# ═══════════════════════════════════════════════════════════════════
# db/models.py — line 56 (repr)
# ═══════════════════════════════════════════════════════════════════
class TestDbModelsRepr:
    def test_task_result_repr(self):
        from backend.db.models import TaskResult
        tr = TaskResult(
            task_id="abc-123",
            status="completed",
            result_data={"text": "hello"},
        )
        r = repr(tr)
        assert "abc-123" in r
