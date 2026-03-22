"""
SPEC-SEARCH-001: 회의록 전문 검색 API

엔드포인트:
- GET /search - FTS5 기반 전문 검색 (REQ-SEARCH-001~005)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.db.search_service import SearchService
from backend.schemas.search import SearchResponse

router = APIRouter(tags=["search"])

# SearchService 인스턴스 (재사용)
_service = SearchService()

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
    db: AsyncSession = Depends(get_db_session),
) -> SearchResponse:
    """
    REQ-SEARCH-001: FTS5 기반 회의록 전문 검색

    회의록(minutes)와 요약(summary) 내용을 검색합니다.
    task_type 파라미터로 특정 유형만 검색할 수 있습니다.

    - q: 검색 쿼리 (2글자 이상, 공백만 있는 경우 422 반환)
    - task_type: 'all', 'minutes', 'summary' 중 하나
    - page: 페이지 번호
    - page_size: 페이지당 결과 수 (최대 50)
    """
    # 공백 제거 후 빈 쿼리 검증
    q = q.strip()
    if not q:
        raise HTTPException(
            status_code=422,
            detail="검색 쿼리는 공백 이외의 문자를 포함해야 합니다.",
        )

    # task_type 유효성 검증
    if task_type not in _VALID_TASK_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"유효하지 않은 task_type입니다. 허용 값: {', '.join(sorted(_VALID_TASK_TYPES))}",
        )

    return await _service.search(
        session=db,
        query=q,
        task_type=task_type,
        page=page,
        page_size=page_size,
    )
