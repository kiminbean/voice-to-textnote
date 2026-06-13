"""커버리지 gap 보충 배치7: remaining 144 lines"""

from unittest.mock import AsyncMock, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# quality_assessment.py — lines 218, 233 (get_improvement_suggestions not_found paths)
# ═══════════════════════════════════════════════════════════════════
class TestQualityAssessmentRemaining:
    @pytest.mark.asyncio
    async def test_get_improvement_suggestions_not_found(self):
        from backend.app.api.v1.audio.quality_assessment import get_improvement_suggestions
        from backend.app.exceptions import NotFoundError
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        svc = AsyncMock()

        with pytest.raises(NotFoundError):
            await get_improvement_suggestions(
                task_id="missing", improvement_type="all", priority="high", db=db, svc=svc,
            )


# ═══════════════════════════════════════════════════════════════════
# keyword_service.py — lines 195-196 (search result accumulation with content)
# ═══════════════════════════════════════════════════════════════════
class TestKeywordServiceSearchWithHits:
    @pytest.mark.asyncio
    async def test_search_finds_keyword_in_content(self):
        from backend.services.keyword_service import KeywordService
        svc = KeywordService()
        result_mock = MagicMock()
        result_mock.task_id = "t1"
        result_mock.created_at = "2026-01-01T00:00:00"
        result_mock.task_type = "stt"

        hits = svc._search_in_text(
            keywords=["테스트"],
            text="안녕하세요 회의 테스트 내용입니다",
            result=result_mock,
            filter=MagicMock(),
        )
        assert len(hits) > 0


# ═══════════════════════════════════════════════════════════════════
# keyword_search.py — line 35 (get_keyword_service factory)
# ═══════════════════════════════════════════════════════════════════
class TestKeywordSearchFactory:
    def test_get_keyword_service(self):
        from backend.app.api.v1.analytics.keyword_search import get_keyword_service
        from backend.services.keyword_service import KeywordService
        result = get_keyword_service()
        assert isinstance(result, KeywordService)


# ═══════════════════════════════════════════════════════════════════
# db/models.py — line 56
# ═══════════════════════════════════════════════════════════════════
class TestDbModelsLine56:
    def test_action_item_repr(self):
        from backend.db.models import ActionItem
        ai = ActionItem(
            id="ai-1",
            title="테스트 액션 아이템",
        )
        r = repr(ai)
        assert isinstance(r, str)


# ═══════════════════════════════════════════════════════════════════
# db/sync_engine.py — line 41
# ═══════════════════════════════════════════════════════════════════
class TestSyncEngineLine41:
    def test_init_sync_engine_idempotent(self):
        import backend.db.sync_engine as mod
        old_engine = mod._initialized_engine
        old_factory = mod._initialized_session_factory
        mod._initialized_engine = None
        mod._initialized_session_factory = None
        try:
            engine1, factory1 = mod.init_sync_engine()
            engine2, factory2 = mod.init_sync_engine()
            assert engine1 is engine2
            assert factory1 is factory2
        finally:
            mod._initialized_engine = old_engine
            mod._initialized_session_factory = old_factory
