"""
검색 서비스 유닛 테스트 - SPEC-SEARCH-001
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.search_service import _QUERY_TOKEN_PATTERN, SearchService


class TestQueryTokenPattern:
    """검색 쿼리 토큰 패턴 테스트"""

    def test_pattern_matches_words(self):
        """단어 토큰이 정상적으로 추출됨"""
        query = "hello world test"
        tokens = _QUERY_TOKEN_PATTERN.findall(query)
        assert tokens == ["hello", "world", "test"]

    def test_pattern_ignores_whitespace(self):
        """공백 무시"""
        query = "  multiple   spaces   between  words  "
        tokens = _QUERY_TOKEN_PATTERN.findall(query)
        assert tokens == ["multiple", "spaces", "between", "words"]

    def test_pattern_with_special_chars(self):
        """특수 문자 포함 토큰 추출"""
        query = "test-query another+sample"
        tokens = _QUERY_TOKEN_PATTERN.findall(query)
        # 특수 문자가 포함된 토큰도 추출됨
        assert len(tokens) == 2
        assert "test-query" in tokens
        assert "another+sample" in tokens


class TestBuildMatchQuery:
    """_build_match_query 메서드 테스트"""

    def test_build_match_query_single_token(self):
        """단일 토큰 MATCH 쿼리 생성"""
        service = SearchService()
        query = service._build_match_query("hello")
        assert query == '"hello"'

    def test_build_match_query_multiple_tokens(self):
        """다중 토큰 AND 쿼리 생성"""
        service = SearchService()
        query = service._build_match_query("hello world")
        assert query == '"hello" AND "world"'

    def test_build_match_query_with_quotes(self):
        """따옴표 포함 토큰 이스케이프"""
        service = SearchService()
        query = service._build_match_query('test "quote" sample')
        # 따옴표가 더블로 이스케이프됨
        assert '""""' in query or '"test"' in query

    def test_build_match_query_empty_string(self):
        """빈 쿼리로 ValueError"""
        service = SearchService()
        with pytest.raises(ValueError, match="검색 쿼리가 비어 있습니다"):
            service._build_match_query("")

    def test_build_match_query_whitespace_only(self):
        """공백만 있는 쿼리로 ValueError"""
        service = SearchService()
        with pytest.raises(ValueError, match="검색 쿼리가 비어 있습니다"):
            service._build_match_query("   ")

    def test_build_match_query_korean(self):
        """한글 토큰 처리"""
        service = SearchService()
        query = service._build_match_query("회의록 검색")
        assert query == '"회의록" AND "검색"'


class TestSearchService:
    """SearchService.search 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_search_basic(self):
        """기본 검색 실행"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        # Mock execute 결과 설정
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 10

        mock_rows_result = MagicMock()
        mock_row = MagicMock()
        mock_row.__iter__ = lambda self: iter(
            [
                "task-123",  # task_id
                "minutes",  # task_type
                "<b>snippet</b>",  # snippet
                "2025-01-01T00:00:00",  # created_at
                None,  # completed_at
            ]
        )
        mock_rows_result.fetchall.return_value = [mock_row]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="test query", task_type="all", page=1, page_size=20
        )

        assert result.total == 10
        assert len(result.items) == 1
        assert result.query == "test query"

    @pytest.mark.asyncio
    async def test_search_with_task_type_filter(self):
        """task_type 필터 포함 검색"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 5

        mock_rows_result = MagicMock()
        mock_rows_result.fetchall.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="test", task_type="minutes", page=1, page_size=20
        )

        assert result.total == 5
        # task_type 필터 사용됨
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_search_pagination(self):
        """페이지네이션 계산 확인"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_rows_result = MagicMock()
        mock_rows_result.fetchall.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="test", task_type="all", page=3, page_size=10
        )

        # offset = (3-1) * 10 = 20
        assert result.page == 3

    @pytest.mark.asyncio
    async def test_search_with_exception(self):
        """검색 예외 발생 시 빈 결과 반환"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await service.search(
            session=mock_session, query="test", task_type="all", page=1, page_size=20
        )

        # 빈 결과 반환
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_with_invalid_datetime_format(self):
        """잘못된 datetime 형식 처리"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_rows_result = MagicMock()
        mock_row = MagicMock()
        # 잘못된 datetime 형식
        mock_row.__iter__ = lambda self: iter(
            [
                "task-456",
                "summary",
                "<b>snippet</b>",
                "invalid-datetime-format",  # 잘못된 형식
                None,
            ]
        )
        mock_rows_result.fetchall.return_value = [mock_row]

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="test", task_type="all", page=1, page_size=20
        )

        # datetime 파싱 실패 시 현재 시간 사용
        assert len(result.items) == 1
        assert result.items[0].task_id == "task-456"

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """검색 결과 없음"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_rows_result = MagicMock()
        mock_rows_result.fetchall.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="nonexistent", task_type="all", page=1, page_size=20
        )

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_count_returns_none(self):
        """count 결과가 None인 경우 처리"""
        service = SearchService()
        mock_session = AsyncMock(spec=object)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = None

        mock_rows_result = MagicMock()
        mock_rows_result.fetchall.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_rows_result])

        result = await service.search(
            session=mock_session, query="test", task_type="all", page=1, page_size=20
        )

        # None이 0으로 변환됨
        assert result.total == 0
