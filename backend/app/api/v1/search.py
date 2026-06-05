"""
SPEC-SEARCH-001/002: 회의록 전문 검색 API

엔드포인트:
- GET /search - FTS5 기반 전문 검색 (REQ-SEARCH-001~005, REQ-SEARCH-007~012)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.app.errors import unprocessable
from backend.schemas.search import SearchResponse, SortOption
from backend.services.search_service import SearchService

router = APIRouter(tags=["search"])


def get_search_service() -> SearchService:
    """SearchService 인스턴스 제공 (FastAPI Depends)"""
    return SearchService()


# 유효한 task_type 값
_VALID_TASK_TYPES = {"all", "summary", "minutes"}


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(
        ...,
        min_length=2,
        description="검색 쿼리 (최소 2글자)",
    ),
    task_type: str = Query(
        default="all",
        description="작업 유형 필터 (all, summary, minutes)",
    ),
    page: int = Query(default=1, ge=1, description="페이지 번호 (1부터 시작)"),
    page_size: int = Query(default=20, ge=1, le=50, description="페이지당 항목 수 (최대 50)"),
    # REQ-SEARCH-007: 날짜 범위 필터
    date_from: datetime | None = Query(None, description="시작 날짜 (ISO 8601)"),
    date_to: datetime | None = Query(None, description="종료 날짜 (ISO 8601)"),
    # REQ-SEARCH-008: 정렬 옵션
    sort: SortOption | None = Query(None, description="정렬 기준 (relevance, newest, oldest)"),
    # REQ-SEARCH-011: 화자 이름 필터
    speaker: str | None = Query(None, description="화자 이름 필터"),
    # REQ-SEARCH-012: 상세 필터
    has_action_items: bool | None = Query(None, description="액션 아이템 존재 여부"),
    has_key_decisions: bool | None = Query(None, description="핵심 결정 존재 여부"),
    db: AsyncSession = Depends(get_db_session),
    svc: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    REQ-SEARCH-001/002: FTS5 기반 회의록 전문 검색 (확장)

    회의록(minutes)와 요약(summary) 내용을 검색합니다.
    다양한 필터와 정렬 옵션을 지원합니다.

    - q: 검색 쿼리 (2글자 이상, 공백만 있는 경우 422 반환)
    - task_type: 'all', 'minutes', 'summary' 중 하나
    - page: 페이지 번호
    - page_size: 페이지당 결과 수 (최대 50)
    - date_from: 시작 날짜 (REQ-SEARCH-007)
    - date_to: 종료 날짜 (REQ-SEARCH-007)
    - sort: 정렬 기준 (relevance, newest, oldest) (REQ-SEARCH-008)
    - speaker: 화자 이름 (REQ-SEARCH-011)
    - has_action_items: 액션 아이템 존재 여부 (REQ-SEARCH-012)
    - has_key_decisions: 핵심 결정 존재 여부 (REQ-SEARCH-012)
    """
    # 공백 제거 후 빈 쿼리 검증
    q = q.strip()
    if not q:
        unprocessable("검색 쿼리는 공백 이외의 문자를 포함해야 합니다.")

    # task_type 유효성 검증
    if task_type not in _VALID_TASK_TYPES:
        unprocessable(
            f"유효하지 않은 task_type입니다. 허용 값: {', '.join(sorted(_VALID_TASK_TYPES))}"
        )

    return await svc.search(
        session=db,
        query=q,
        task_type=task_type,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        speaker=speaker,
        has_action_items=has_action_items,
        has_key_decisions=has_key_decisions,
    )
