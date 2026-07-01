"""
SPEC-RELATED-001: 관련 회의 추천(Related Meetings) 서비스

기준 회의(task_id)의 상위 키워드를 이용해 FTS5 search_index에서 유사한 다른
회의를 찾는다. 새로운 임베딩/외부 의존성 없이 기존 자산을 재사용한다:
- 키워드 추출: KeywordService (TF-IDF + TextRank)
- FTS MATCH 쿼리 이스케이핑/접근제어: SearchService의 검증된 헬퍼

# @MX:NOTE: [AUTO] 회의↔회의 유사도 탐색 진입점. FTS bm25 rank + 공유 키워드 비율로 정렬한다.
# @MX:SPEC: SPEC-RELATED-001
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.schemas.related_meetings import RelatedMeetingItem, RelatedMeetingsResponse
from backend.services.keyword_service import KeywordService
from backend.services.search_service import SearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 공유 키워드 계산용 토큰 패턴 (한글/영문/숫자 단어)
_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
# 키워드 추출을 시도하기 위한 최소 텍스트 길이 (KeywordService 최소 요건과 정렬)
_MIN_SOURCE_TEXT_LEN = 10


class RelatedMeetingsService:
    """FTS5 + 키워드 기반 관련 회의 추천 서비스 (SPEC-RELATED-001)"""

    def __init__(self, keyword_service: KeywordService | None = None) -> None:
        self._keyword_service = keyword_service or KeywordService()

    async def find_related(
        self,
        session: AsyncSession,
        source_task_id: str,
        *,
        limit: int | None = None,
        owner_id: UUID | str | None = None,
        guest_session_id: str | None = None,
    ) -> RelatedMeetingsResponse:
        """
        기준 회의와 관련된 다른 회의를 찾는다.

        Args:
            session: 비동기 SQLAlchemy 세션
            source_task_id: 기준 회의 task_id
            limit: 반환할 최대 회의 수 (None이면 설정 기본값)
            owner_id: 로그인 사용자 ID (접근 가능 회의로 제한)
            guest_session_id: 게스트 세션 ID (게스트 소유 회의로 제한)

        Returns:
            RelatedMeetingsResponse. 근거가 없으면 빈 items를 반환한다.
        """
        effective_limit = limit or settings.related_meetings_default_limit

        # 1. 기준 회의의 인덱싱된 텍스트를 로드
        source_text = await self._load_source_text(session, source_task_id)
        empty = RelatedMeetingsResponse(source_task_id=source_task_id, keywords=[], items=[], total=0)
        if len(source_text.strip()) < _MIN_SOURCE_TEXT_LEN:
            return empty

        # 2. 상위 키워드 추출 (기존 KeywordService 재사용)
        keywords = self._extract_keywords(source_text)
        if not keywords:
            return empty

        # 3. 관련 회의 후보 조회 (자기 자신 제외 + 접근제어 적용)
        rows = await self._query_candidates(
            session,
            keywords=keywords,
            source_task_id=source_task_id,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
        )

        # 4. task_id 단위로 dedupe, 공유 키워드/점수 계산, 정렬, 상한 적용
        items = self._rank_candidates(rows, keywords, effective_limit)

        return RelatedMeetingsResponse(
            source_task_id=source_task_id,
            keywords=keywords,
            items=items,
            total=len(items),
        )

    async def _load_source_text(self, session: AsyncSession, source_task_id: str) -> str:
        """기준 회의의 인덱싱된 모든 텍스트 컬럼을 합쳐 반환한다."""
        sql = """
        SELECT
            COALESCE(content, '') || ' ' ||
            COALESCE(summary_text, '') || ' ' ||
            COALESCE(action_items_text, '') AS all_text
        FROM search_index
        WHERE task_id = :task_id
        """
        try:
            result = await session.execute(text(sql), {"task_id": source_task_id})
            rows = result.fetchall()
        except Exception as e:  # pragma: no cover - 인덱스 부재 등 방어적 처리
            logger.warning("기준 회의 텍스트 로드 실패", task_id=source_task_id, error=str(e))
            return ""
        return " ".join(str(row[0]) for row in rows if row[0])

    def _extract_keywords(self, source_text: str) -> list[str]:
        """기준 텍스트에서 상위 키워드 term 목록을 추출한다."""
        try:
            response = self._keyword_service.extract_from_text(
                source_text,
                max_keywords=settings.related_meetings_keyword_count,
                source="meeting",
            )
        except Exception as e:  # pragma: no cover - 짧은 텍스트 등에서 방어적 처리
            logger.warning("관련 회의 키워드 추출 실패", error=str(e))
            return []
        return [item.keyword for item in response.keywords if item.keyword]

    async def _query_candidates(
        self,
        session: AsyncSession,
        *,
        keywords: list[str],
        source_task_id: str,
        owner_id: UUID | str | None,
        guest_session_id: str | None,
    ) -> list[Any]:
        """FTS MATCH로 기준 회의를 제외한 후보 행을 조회한다."""
        match_query = SearchService._build_any_match_query(" ".join(keywords))
        params: dict[str, Any] = {"query": match_query, "source_task_id": source_task_id}

        where_conditions = ["search_index MATCH :query", "si.task_id != :source_task_id"]
        visibility_clause = SearchService._build_visibility_clause(
            owner_id, guest_session_id, params
        )
        if visibility_clause:
            where_conditions.append(visibility_clause)
        where_clause = " AND ".join(where_conditions)

        # dedupe/필터 여유분을 위해 요청 상한보다 넉넉히 조회한다.
        fetch_limit = max(settings.related_meetings_max_limit * 3, 60)
        params["fetch_limit"] = fetch_limit

        sql = f"""
        SELECT
            si.task_id,
            si.task_type,
            CASE
                WHEN si.task_type = 'summary'
                THEN snippet(search_index, 4, '<b>', '</b>', '...', 30)
                ELSE snippet(search_index, 2, '<b>', '</b>', '...', 30)
            END AS snippet,
            si.created_at,
            tr.completed_at,
            COALESCE(si.content, '') || ' ' ||
            COALESCE(si.summary_text, '') || ' ' ||
            COALESCE(si.action_items_text, '') || ' ' ||
            COALESCE(si.speaker_names, '') AS all_text,
            rank
        FROM search_index si
        LEFT JOIN task_results tr ON si.task_id = tr.task_id
        WHERE {where_clause}
        ORDER BY rank ASC, si.created_at DESC
        LIMIT :fetch_limit
        """
        try:
            result = await session.execute(text(sql), params)
            return result.fetchall()
        except Exception as e:
            logger.warning(
                "관련 회의 후보 조회 실패",
                source_task_id=source_task_id,
                error=str(e),
            )
            return []

    def _rank_candidates(
        self,
        rows: list[Any],
        keywords: list[str],
        limit: int,
    ) -> list[RelatedMeetingItem]:
        """후보 행을 task_id 단위로 정리하고 공유 키워드/점수로 정렬한다."""
        keyword_tokens = self._keyword_token_set(keywords)
        if not keyword_tokens:
            return []

        min_shared = settings.related_meetings_min_shared
        best_by_task: dict[str, RelatedMeetingItem] = {}

        for task_id, task_type, snippet, created_at_raw, completed_at, all_text, _rank in rows:
            row_tokens = {
                token.lower() for token in _TOKEN_PATTERN.findall(all_text or "")
            }
            shared = sorted(keyword_tokens & row_tokens)
            if len(shared) < min_shared:
                continue

            score = min(len(shared) / len(keyword_tokens), 1.0)
            created_at = self._parse_datetime(created_at_raw)

            item = RelatedMeetingItem(
                task_id=task_id,
                task_type=task_type,
                snippet=snippet or "",
                shared_keywords=shared,
                score=round(score, 4),
                created_at=created_at,
                completed_at=completed_at,
            )

            # 같은 회의(task_id)에 minutes/summary 행이 모두 있을 수 있으므로
            # 공유 키워드가 더 많은(=score 높은) 행을 대표로 남긴다.
            existing = best_by_task.get(task_id)
            if existing is None or item.score > existing.score:
                best_by_task[task_id] = item

        ranked = sorted(
            best_by_task.values(),
            key=lambda it: (it.score, it.created_at),
            reverse=True,
        )
        return ranked[:limit]

    @staticmethod
    def _keyword_token_set(keywords: list[str]) -> set[str]:
        """키워드(구문 포함)를 소문자 단어 토큰 집합으로 변환한다."""
        tokens: set[str] = set()
        for keyword in keywords:
            for token in _TOKEN_PATTERN.findall(keyword):
                tokens.add(token.lower())
        return tokens

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        """created_at 문자열/객체를 datetime으로 변환한다."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:  # pragma: no cover - 방어적 처리
                return datetime.now(UTC).replace(tzinfo=None)
        return datetime.now(UTC).replace(tzinfo=None)  # pragma: no cover
