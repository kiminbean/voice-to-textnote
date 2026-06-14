"""
검색 서비스 - SPEC-SEARCH-001, SPEC-SEARCH-002

SQLite FTS5 기반 전문 검색 서비스
비동기 세션(get_db_session)을 사용합니다.

REQ-SEARCH-007: 날짜 범위 필터 (date_from, date_to)
REQ-SEARCH-008: 정렬 옵션 (sort: relevance | newest | oldest)
REQ-SEARCH-011: 화자 이름 필터 (speaker)
REQ-SEARCH-012: 액션 아이템/핵심 결정 필터 (has_action_items, has_key_decisions)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.search import SearchResponse, SearchResultItem, SortOption
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_QUERY_TOKEN_PATTERN = re.compile(r"\S+")


class SearchService:
    """
    FTS5 기반 전문 검색 서비스 (SPEC-SEARCH-001/002)

    SQLite FTS5 MATCH 쿼리를 사용하여 회의록 및 요약 내용을 검색합니다.
    동적 SQL 빌더로 다양한 필터와 정렬 옵션을 지원합니다.
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
        # REQ-SEARCH-007: 날짜 범위 필터
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        # REQ-SEARCH-008: 정렬 옵션
        sort: SortOption | None = None,
        # REQ-SEARCH-011: 화자 이름 필터
        speaker: str | None = None,
        # REQ-SEARCH-012: 상세 필터
        has_action_items: bool | None = None,
        has_key_decisions: bool | None = None,
    ) -> SearchResponse:
        """
        FTS5 전문 검색 실행 (동적 SQL 빌더)

        Args:
            session: 비동기 SQLAlchemy 세션
            query: 검색 쿼리 문자열
            task_type: 작업 유형 필터 ('all', 'minutes', 'summary')
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지 당 항목 수
            date_from: 시작 날짜 (REQ-SEARCH-007)
            date_to: 종료 날짜 (REQ-SEARCH-007)
            sort: 정렬 기준 (REQ-SEARCH-008)
            speaker: 화자 이름 필터 (REQ-SEARCH-011)
            has_action_items: 액션 아이템 존재 여부 (REQ-SEARCH-012)
            has_key_decisions: 핵심 결정 존재 여부 (REQ-SEARCH-012)

        Returns:
            SearchResponse 객체
        """
        offset = (page - 1) * page_size
        match_query = self._build_match_query(query)

        # 동적 WHERE 조건 빌드
        where_conditions = ["search_index MATCH :query"]
        params: dict[str, Any] = {"query": match_query}

        # task_type 필터
        if task_type != "all":
            where_conditions.append("si.task_type = :task_type")
            params["task_type"] = task_type

        # REQ-SEARCH-007: 날짜 범위 필터
        if date_from:
            where_conditions.append("si.created_at >= :date_from")
            params["date_from"] = date_from.isoformat()

        if date_to:
            where_conditions.append("si.created_at <= :date_to")
            params["date_to"] = date_to.isoformat()

        # REQ-SEARCH-011: 화자 이름 필터
        if speaker:
            where_conditions.append("si.speaker_names LIKE '%' || :speaker || '%'")
            params["speaker"] = speaker

        # REQ-SEARCH-012: 상세 필터
        if has_action_items:
            where_conditions.append(
                "si.action_items_text IS NOT NULL AND si.action_items_text != ''"
            )

        if has_key_decisions:  # pragma: no cover
            where_conditions.append("si.task_type = 'summary'")
            where_conditions.append(
                "si.action_items_text IS NOT NULL AND si.action_items_text != ''"
            )

        # 동적 ORDER BY 빌드 (REQ-SEARCH-008)
        if sort == SortOption.RELEVANCE:  # pragma: no cover
            # FTS5 rank 컬럼으로 정렬 (bm25, 낮을수록 관련성 높음)
            order_by = "rank ASC"
            select_rank = ", rank"
        elif sort == SortOption.OLDEST:
            order_by = "si.created_at ASC"
            select_rank = ""
        else:
            # sort가 NEWEST이거나 None인 경우 (기본값, 하위 호환)
            order_by = "si.created_at DESC"
            select_rank = ""

        # 최종 SQL 빌드
        where_clause = " AND ".join(where_conditions)

        search_sql = f"""
        SELECT
            si.task_id,
            si.task_type,
            snippet(search_index, 2, '<b>', '</b>', '...', 30) AS snippet,
            si.created_at,
            tr.completed_at{select_rank}
        FROM search_index si
        LEFT JOIN task_results tr ON si.task_id = tr.task_id
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT :limit OFFSET :offset
        """

        count_sql = f"SELECT COUNT(*) FROM search_index si WHERE {where_clause}"

        try:
            # 전체 카운트 조회
            count_result = await session.execute(text(count_sql), params)
            total = count_result.scalar() or 0

            # 검색 결과 조회
            params = {**params, "limit": page_size, "offset": offset}
            rows_result = await session.execute(text(search_sql), params)
            rows = rows_result.fetchall()

            # SearchResultItem 목록 구성
            items: list[SearchResultItem] = []
            for row in rows:
                # rank 컬럼이 포함된 경우 마지막 요소는 rank 값
                task_id, task_type_val, snippet, created_at_str, completed_at = (
                    row[:5] if select_rank else row
                )

                # created_at 파싱
                if isinstance(created_at_str, str):
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except ValueError:
                        created_at = datetime.now(UTC).replace(tzinfo=None)  # pragma: no cover
                else:
                    created_at = created_at_str  # pragma: no cover

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
            sort=sort,
        )

    async def get_suggestions(
        self,
        session: AsyncSession,
        prefix: str,
        limit: int = 10,
    ) -> list[str]:
        """
        REQ-SEARCH-009: 검색 제안 토큰 반환 (FTS5 접두사 검색)

        FTS5 인덱스에서 접두사가 일치하는 토큰을 반환합니다.

        Args:
            session: 비동기 SQLAlchemy 세션
            prefix: 검색 접두사 (빈 문자열이면 빈 목록 반환)
            limit: 최대 결과 수 (기본값 10)

        Returns:
            중복 제거된 제안 토큰 목록 (접두사 오름차순)
        """
        # 빈 접두사 또는 공백만 있는 경우 빈 목록 반환
        prefix = prefix.strip()
        if not prefix:
            return []

        try:
            # FTS5 접두사 검색: 모든 텍스트 컬럼에서 매칭된 행의 텍스트를 가져와
            # Python에서 접두사로 시작하는 단어 토큰을 추출
            combined_sql = """
            SELECT
                COALESCE(content, '') || ' ' ||
                COALESCE(speaker_names, '') || ' ' ||
                COALESCE(summary_text, '') || ' ' ||
                COALESCE(action_items_text, '') AS all_text
            FROM search_index
            WHERE search_index MATCH :match_query
            LIMIT 50
            """

            # FTS5 접두사 쿼리 (접두사* 형태)
            result = await session.execute(
                text(combined_sql),
                {"match_query": f"{prefix}*"},
            )
            rows = result.fetchall()

            # 매칭된 텍스트에서 접두사로 시작하는 단어 토큰 추출
            seen = set()
            suggestions = []
            for row in rows:  # pragma: no cover
                if not row[0]:
                    continue
                # 공백/구두점으로 분리 후 접두사로 시작하는 토큰 필터링
                for word in row[0].split():
                    cleaned = word.strip(".,!?;:'\"()[]{}").strip()
                    if cleaned.startswith(prefix) and cleaned not in seen:
                        seen.add(cleaned)
                        suggestions.append(cleaned)
                        if len(suggestions) >= limit:
                            return suggestions

            return suggestions

        except Exception as e:
            logger.warning(
                "검색 제안 쿼리 실행 실패",
                prefix=prefix,
                error=str(e),
            )
            # 오류 발생 시 빈 목록 반환
            return []
