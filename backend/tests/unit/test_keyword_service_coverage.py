"""keyword_service.py 커버리지 100% 테스트"""

import json
from collections import Counter
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas.keyword import (
    KeywordExtractRequest,
    KeywordHit,
    KeywordItem,
    KeywordRecommendRequest,
    KeywordResponse,
    KeywordSearchFilter,
    KeywordSearchResponse,
    KeywordStatsResponse,
    KeywordSuggestResponse,
    SortOption,
)
from backend.services.keyword_service import KeywordService


# ── helpers ──────────────────────────────────────────────────────────
def _svc() -> KeywordService:
    return KeywordService()


def _mock_task_result(task_id="t1", task_type="minutes", result_data=None, created_at=None):
    tr = MagicMock()
    tr.task_id = task_id
    tr.task_type = task_type
    tr.result_data = result_data or {}
    tr.created_at = created_at or datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    return tr


# ── __init__ / _extract_keywords / _generate_variations ─────────────
class TestInitAndExtract:
    def test_init(self):
        svc = _svc()
        assert svc.korean_pattern is not None
        assert "그리고" in svc.stop_words

    def test_extract_keywords_empty(self):
        assert _svc()._extract_keywords("") == []

    def test_extract_keywords_korean(self):
        kw = _svc()._extract_keywords("프로젝트 일정 관리")
        assert "프로젝트" in kw

    def test_extract_keywords_filters_stopwords(self):
        kw = _svc()._extract_keywords("그리고 모든 문제")
        assert "그리고" not in kw

    def test_extract_keywords_no_variations(self):
        kw = _svc()._extract_keywords("프로젝트 일정", include_variations=False)
        assert all(not k.endswith("기") for k in kw)

    def test_generate_variations(self):
        v = _svc()._generate_variations(["테스트"])
        assert any(x.endswith("기") for x in v)
        assert any(x.endswith("들") for x in v)
        assert any(x.endswith("하는") for x in v)

    def test_generate_variations_short_keyword(self):
        v = _svc()._generate_variations(["ab"])
        # len < 3 → no "하는" suffix
        assert not any(x.endswith("하는") for x in v)

    def test_generate_variations_ends_with_gi(self):
        v = _svc()._generate_variations(["테스트하기"])
        assert not any(x == "테스트하기기" for x in v)

    def test_generate_variations_ends_with_deul(self):
        v = _svc()._generate_variations(["테스트들"])
        assert not any(x == "테스트들들" for x in v)


# ── _calculate_relevance_score ───────────────────────────────────────
class TestRelevanceScore:
    def test_basic(self):
        svc = _svc()
        score = svc._calculate_relevance_score(
            keyword="프로젝트", text_content="프로젝트 일정 관리",
            title="title", frequency=1, is_exact_match=False
        )
        assert isinstance(score, float)
        assert 0 <= score <= 1


# ── search_keywords ──────────────────────────────────────────────────
def _async_session(results=None):
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=results or [])
        ))
    ))
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    session.query.return_value = q
    return session


class TestSearchKeywords:
    @pytest.mark.asyncio
    async def test_search_basic(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정 관리 회의"})
        session = _async_session([tr])
        filt = KeywordSearchFilter()
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.relevance)
        assert isinstance(resp, KeywordSearchResponse)
        assert resp.total_hits == 0

    @pytest.mark.asyncio
    async def test_search_with_date_filter(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content here"})
        session = _async_session([tr])
        filt = KeywordSearchFilter(
            date_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.newest)
        assert isinstance(resp, KeywordSearchResponse)

    @pytest.mark.asyncio
    async def test_search_sort_oldest(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content"})
        session = _async_session([tr])
        filt = KeywordSearchFilter()
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.oldest)
        assert isinstance(resp, KeywordSearchResponse)

    @pytest.mark.asyncio
    async def test_search_sort_frequency(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content"})
        session = _async_session([tr])
        filt = KeywordSearchFilter()
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.frequency)
        assert isinstance(resp, KeywordSearchResponse)

    @pytest.mark.asyncio
    async def test_search_with_task_type_filter(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content"})
        session = _async_session([tr])
        filt = KeywordSearchFilter(task_types=["minutes"])
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.relevance)
        assert isinstance(resp, KeywordSearchResponse)

    @pytest.mark.asyncio
    async def test_search_date_from_only(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content"})
        session = _async_session([tr])
        filt = KeywordSearchFilter(date_from=datetime(2026, 1, 1, tzinfo=timezone.utc))
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.relevance)
        assert isinstance(resp, KeywordSearchResponse)

    @pytest.mark.asyncio
    async def test_search_date_to_only(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "test content"})
        session = _async_session([tr])
        filt = KeywordSearchFilter(date_to=datetime(2026, 12, 31, tzinfo=timezone.utc))
        resp = await svc.search_keywords(session, ["xyznotfound"], filt, page=1, page_size=10, sort=SortOption.relevance)
        assert isinstance(resp, KeywordSearchResponse)


# ── _extract_text_from_result ────────────────────────────────────────
class TestExtractTextFromResult:
    def test_minutes_dict(self):
        text = _svc()._extract_text_from_result({"minutes": {"content": "hello", "summary": "world"}})
        assert "hello" in text and "world" in text

    def test_minutes_string(self):
        text = _svc()._extract_text_from_result({"minutes": "plain minutes"})
        assert "plain minutes" in text

    def test_summary_string(self):
        text = _svc()._extract_text_from_result({"summary": "summary text"})
        assert "summary text" in text

    def test_summary_dict(self):
        text = _svc()._extract_text_from_result({"summary": {"content": "c", "summary": "s"}})
        assert "c" in text and "s" in text

    def test_transcription_segments(self):
        text = _svc()._extract_text_from_result({"transcription": {"segments": [{"text": "seg1"}, {"text": "seg2"}]}})
        assert "seg1" in text

    def test_keywords_list(self):
        text = _svc()._extract_text_from_result({"keywords": ["kw1", "kw2"]})
        assert "kw1" in text

    def test_empty(self):
        assert _svc()._extract_text_from_result({}) == ""


# ── _search_in_text ──────────────────────────────────────────────────
class TestSearchInText:
    def test_found(self):
        svc = _svc()
        tr = _mock_task_result()
        hits = svc._search_in_text(["hello"], "hello world test hello", tr, KeywordSearchFilter())
        assert len(hits) == 1
        assert hits[0].frequency == 2

    def test_not_found(self):
        svc = _svc()
        tr = _mock_task_result()
        hits = svc._search_in_text(["xyz"], "hello world", tr, KeywordSearchFilter())
        assert hits == []

    def test_exact_match(self):
        svc = _svc()
        tr = _mock_task_result()
        hits = svc._search_in_text(["hello"], "Hello World", tr, KeywordSearchFilter(exact_match=True))
        assert len(hits) == 1

    def test_many_positions_capped_at_5(self):
        svc = _svc()
        tr = _mock_task_result()
        text = "hello " * 10
        hits = svc._search_in_text(["hello"], text, tr, KeywordSearchFilter())
        assert len(hits[0].context_before) <= 5


# ── _sort_search_results ────────────────────────────────────────────
class TestSortSearchResults:
    def _make_hit(self, score, freq, dt):
        return KeywordHit(
            task_id="t", task_type="minutes", title="t",
            positions=[], context_before=[], context_after=[],
            created_at=dt, speakers=[], duration=None,
            relevance_score=score, frequency=freq, has_highlights=False,
        )

    def test_sort_relevance(self):
        svc = _svc()
        h1 = self._make_hit(0.5, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        h2 = self._make_hit(0.9, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = svc._sort_search_results([h1, h2], SortOption.relevance)
        assert result[0].relevance_score == 0.9

    def test_sort_frequency(self):
        svc = _svc()
        h1 = self._make_hit(0.5, 3, datetime(2026, 1, 1, tzinfo=timezone.utc))
        h2 = self._make_hit(0.9, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = svc._sort_search_results([h1, h2], SortOption.frequency)
        assert result[0].frequency == 3

    def test_sort_newest(self):
        svc = _svc()
        h1 = self._make_hit(0.5, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        h2 = self._make_hit(0.5, 1, datetime(2026, 6, 1, tzinfo=timezone.utc))
        result = svc._sort_search_results([h1, h2], SortOption.newest)
        assert result[0].created_at.month == 6

    def test_sort_oldest(self):
        svc = _svc()
        h1 = self._make_hit(0.5, 1, datetime(2026, 6, 1, tzinfo=timezone.utc))
        h2 = self._make_hit(0.5, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = svc._sort_search_results([h1, h2], SortOption.oldest)
        assert result[0].created_at.month == 1

    def test_sort_default(self):
        svc = _svc()
        hits = [self._make_hit(0.5, 1, datetime(2026, 1, 1, tzinfo=timezone.utc))]
        result = svc._sort_search_results(hits, "unknown")
        assert result == hits


# ── _calculate_keyword_stats ────────────────────────────────────────
class TestCalculateKeywordStats:
    def test_basic(self):
        svc = _svc()
        hit = KeywordHit(
            task_id="t1", task_type="minutes", title="test keyword",
            positions=[0], context_before=[], context_after=[],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            speakers=[], duration=None, relevance_score=0.8, frequency=2, has_highlights=False,
        )
        stats = svc._calculate_keyword_stats([hit], ["test"])
        assert "test" in stats
        assert stats["test"]["total_hits"] == 1


# ── suggest_keywords ─────────────────────────────────────────────────
class TestSuggestKeywords:
    @pytest.mark.asyncio
    async def test_suggest(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정 관리"})
        session = _async_session([tr])
        resp = await svc.suggest_keywords(session, "프로젝트", limit=5, include_synonyms=False)
        assert isinstance(resp, KeywordSuggestResponse)

    @pytest.mark.asyncio
    async def test_suggest_with_synonyms(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "개발 설계 테스트"})
        session = _async_session([tr])
        resp = await svc.suggest_keywords(session, "프로젝트", limit=5, include_synonyms=True)
        assert isinstance(resp, KeywordSuggestResponse)


# ── get_keyword_stats ────────────────────────────────────────────────
class TestGetKeywordStats:
    @pytest.mark.asyncio
    async def test_stats(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정 관리 프로젝트"})
        session = _async_session([tr])
        resp = await svc.get_keyword_stats(
            session,
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
            top_n=10, include_trends=True,
        )
        assert isinstance(resp, KeywordStatsResponse)


# ── _get_keyword_frequency ──────────────────────────────────────────
class TestGetKeywordFrequency:
    @pytest.mark.asyncio
    async def test_no_date_filter(self):
        svc = _svc()
        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정"})
        session = _async_session([tr])
        freq = await svc._get_keyword_frequency(session)
        assert isinstance(freq, dict)


# ── _find_synonyms / _find_related_keywords ─────────────────────────
class TestSynonymsAndRelated:
    def test_known_synonym(self):
        assert len(_svc()._find_synonyms("개발")) > 0

    def test_unknown_synonym(self):
        assert _svc()._find_synonyms("unknown") == []

    def test_known_related(self):
        assert len(_svc()._find_related_keywords("개발")) > 0

    def test_unknown_related(self):
        assert _svc()._find_related_keywords("unknown") == []


# ── _score_keywords ──────────────────────────────────────────────────
class TestScoreKeywords:
    def test_basic(self):
        svc = _svc()
        items = svc._score_keywords("text", ["a", "b", "a"])
        assert len(items) == 2
        assert all(isinstance(i, KeywordItem) for i in items)

    def test_empty(self):
        svc = _svc()
        items = svc._score_keywords("", [])
        assert items == []


# ── extract_from_text ────────────────────────────────────────────────
class TestExtractFromText:
    def test_basic(self):
        svc = _svc()
        resp = svc.extract_from_text("프로젝트 일정 관리 회의")
        assert isinstance(resp, KeywordResponse)
        assert resp.source == "text"
        assert resp.language == "ko"

    def test_with_params(self):
        svc = _svc()
        resp = svc.extract_from_text("프로젝트", max_keywords=5, min_score=0.0, source="manual")
        assert isinstance(resp, KeywordResponse)
        assert resp.source == "manual"


# ── extract_for_task ─────────────────────────────────────────────────
class TestExtractForTask:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        svc = _svc()
        redis = AsyncMock()
        cached_resp = KeywordResponse(keywords=[KeywordItem(keyword="kw", score=0.9, frequency=1)], total_count=1, source="task", language="ko")
        redis.get.return_value = cached_resp.model_dump_json()

        db = AsyncMock()
        resp = await svc.extract_for_task(redis_client=redis, db=db, task_id="t1")
        assert isinstance(resp, KeywordResponse)

    @pytest.mark.asyncio
    async def test_task_not_found(self):
        svc = _svc()
        redis = AsyncMock()
        redis.get.return_value = None

        db = AsyncMock()
        db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        )

        resp = await svc.extract_for_task(redis_client=redis, db=db, task_id="missing")
        assert resp.total_count == 0

    @pytest.mark.asyncio
    async def test_task_no_content(self):
        svc = _svc()
        redis = AsyncMock()
        redis.get.return_value = None

        tr = _mock_task_result(result_data={})
        db = AsyncMock()
        db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=tr)))
        )

        resp = await svc.extract_for_task(redis_client=redis, db=db, task_id="t1")
        assert resp.total_count == 0

    @pytest.mark.asyncio
    async def test_task_with_content(self):
        svc = _svc()
        redis = AsyncMock()
        redis.get.return_value = None
        redis.setex = AsyncMock()

        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정 관리 회의"})
        db = AsyncMock()
        db.execute.return_value = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=tr)))
        )

        resp = await svc.extract_for_task(redis_client=redis, db=db, task_id="t1")
        assert isinstance(resp, KeywordResponse)
        redis.setex.assert_called_once()


# ── recommend_for_task ───────────────────────────────────────────────
class TestRecommendForTask:
    @pytest.mark.asyncio
    async def test_basic(self):
        svc = _svc()
        redis = AsyncMock()
        redis.get.return_value = None
        redis.setex = AsyncMock()

        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정 관리"})
        db = AsyncMock()

        scalars_first = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=tr)))
        )
        scalars_all = MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[tr])))
        )

        db.execute.side_effect = [scalars_first, scalars_all]

        resp = await svc.recommend_for_task(redis_client=redis, db=db, task_id="t1")
        assert isinstance(resp, KeywordResponse)
        assert resp.source == "recommend"

    @pytest.mark.asyncio
    async def test_db_error_falls_back(self):
        svc = _svc()
        redis = AsyncMock()
        redis.get.return_value = None
        redis.setex = AsyncMock()

        tr = _mock_task_result(result_data={"minutes": "프로젝트 일정"})
        db = AsyncMock()

        scalars_first = MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=tr)))
        )

        db.execute.side_effect = [scalars_first, Exception("db error")]

        resp = await svc.recommend_for_task(redis_client=redis, db=db, task_id="t1")
        assert isinstance(resp, KeywordResponse)
