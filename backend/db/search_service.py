"""
검색 서비스 - SPEC-SEARCH-001

SQLite FTS5 기반 전문 검색 서비스
비동기 세션(get_db_session)을 사용합니다.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.search import SearchResponse, SearchResultItem
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# FTS5 스니펫 검색 쿼리 (completed_at은 task_results 테이블 조인)
_SEARCH_SQL = """
SELECT
    si.task_id,
    si.task_type,
    snippet(search_index, 2, '<b>', '</b>', '...', 30) AS snippet,
    si.created_at,
    tr.completed_at
FROM search_index si
LEFT JOIN task_results tr ON si.task_id = tr.task_id
WHERE search_index MATCH :query
ORDER BY si.created_at DESC
LIMIT :limit OFFSET :offset
"""

# task_type 필터 포함 검색 쿼리
_SEARCH_SQL_WITH_TYPE = """
SELECT
    si.task_id,
    si.task_type,
    snippet(search_index, 2, '<b>', '</b>', '...', 30) AS snippet,
    si.created_at,
    tr.completed_at
FROM search_index si
LEFT JOIN task_results tr ON si.task_id = tr.task_id
WHERE search_index MATCH :query
AND si.task_type = :task_type
ORDER BY si.created_at DESC
LIMIT :limit OFFSET :offset
"""

# 전체 카운트 쿼리
_COUNT_SQL = "SELECT COUNT(*) FROM search_index WHERE search_index MATCH :query"

# task_type 필터 포함 카운트 쿼리
_COUNT_SQL_WITH_TYPE = """
SELECT COUNT(*) FROM search_index
WHERE search_index MATCH :query
AND task_type = :task_type
"""

_QUERY_TOKEN_PATTERN = re.compile(r"\S+")


class SearchService:
    """
    FTS5 기반 전문 검색 서비스

    SQLite FTS5 MATCH 쿼리를 사용하여 회의록 및 요약 내용을 검색합니다.
    """

    @staticmethod
    def _build_match_query(query: str) -> str:
        """
        사용자 입력을 안전한 FTS5 MATCH 쿼리로 변환합니다.

        FTS 연산자/구문을 그대로 통과시키지 않고 토큰 단위로 quoting하여
        구문 오류와 의도치 않은 MATCH 조작을 방지합니다.
        """
        tokens = _QUERY_TOKEN_PATTERN.findall(query)
        if not tokens:
            raise ValueError("검색 쿼리가 비어 있습니다")

        escaped_tokens = [f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens]
        return " AND ".join(escaped_tokens)

    async def search(
        self,
        session: AsyncSession,
        query: str,
        task_type: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse:
        """
        FTS5 전문 검색 실행

        Args:
            session: 비동기 SQLAlchemy 세션
            query: 검색 쿼리 문자열
            task_type: 작업 유형 필터 ('all', 'minutes', 'summary')
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지 당 항목 수

        Returns:
            SearchResponse 객체
        """
        offset = (page - 1) * page_size
        use_type_filter = task_type != "all"
        match_query = self._build_match_query(query)

        try:
            # 전체 카운트 조회
            if use_type_filter:
                count_result = await session.execute(
                    text(_COUNT_SQL_WITH_TYPE),
                    {"query": match_query, "task_type": task_type},
                )
            else:
                count_result = await session.execute(
                    text(_COUNT_SQL),
                    {"query": match_query},
                )
            total = count_result.scalar() or 0

            # 검색 결과 조회
            if use_type_filter:
                rows_result = await session.execute(
                    text(_SEARCH_SQL_WITH_TYPE),
                    {
                        "query": match_query,
                        "task_type": task_type,
                        "limit": page_size,
                        "offset": offset,
                    },
                )
            else:
                rows_result = await session.execute(
                    text(_SEARCH_SQL),
                    {
                        "query": match_query,
                        "limit": page_size,
                        "offset": offset,
                    },
                )

            rows = rows_result.fetchall()

            # SearchResultItem 목록 구성
            items: list[SearchResultItem] = []
            for row in rows:
                task_id, task_type_val, snippet, created_at_str, completed_at = row

                # created_at 파싱
                if isinstance(created_at_str, str):
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except ValueError:
                        created_at = datetime.now(UTC).replace(tzinfo=None)
                else:
                    created_at = created_at_str

                items.append(
                    SearchResultItem(
                        task_id=task_id,
                        task_type=task_type_val,
                        snippet=snippet or "",
                        created_at=created_at,
                        completed_at=completed_at,
                    )
                )

        except Exception as e:
            logger.warning(
                "검색 쿼리 실행 실패",
                query=query,
                task_type=task_type,
                error=str(e),
            )
            # 빈 결과 반환 (검색 인덱스가 없는 경우 포함)
            total = 0
            items = []

        return SearchResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            query=query,
        )
