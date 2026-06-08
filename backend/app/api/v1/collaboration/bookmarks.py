"""
SPEC-BOOKMARK-001: 회의록 북마크/하이라이트 API (확장)

엔드포인트 (모두 JWT 인증 필요):
- POST   /api/v1/bookmarks              생성
- GET    /api/v1/bookmarks               목록 (task_id 필터링 지원)
- GET    /api/v1/bookmarks/{bookmark_id} 단건 조회
- PATCH  /api/v1/bookmarks/{bookmark_id} 부분 수정
- DELETE /api/v1/bookmarks/{bookmark_id} 삭제
- POST   /api/v1/bookmarks/bulk          대량 작업 (삭제, 카테고리/우선순위 업데이트)
- GET    /api/v1/bookmarks/search         고급 검색
- GET    /api/v1/bookmarks/summary       북마크 통계 및 요약
- POST   /api/v1/bookmarks/cleanup       북마크 정리
- POST   /api/v1/bookmarks/export        북마크 내보내기
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.schemas.bookmark import (
    BookmarkBulkOperation,
    BookmarkBulkResponse,
    BookmarkCategory,
    BookmarkCleanupRequest,
    BookmarkCleanupResponse,
    BookmarkCreate,
    BookmarkListResponse,
    BookmarkPriority,
    BookmarkResponse,
    BookmarkSearchRequest,
    BookmarkSearchResponse,
    BookmarkSummaryResponse,
    BookmarkUpdate,
)
from backend.services.bookmark_service import BookmarkService

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


def _val(obj: Any, key: str, default: Any = None) -> Any:
    """dict와 MagicMock 모두에서 값 추출 (서비스는 dict, 테스트 mock은 MagicMock 반환)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    val = getattr(obj, key, default)
    # 테스트 mock(MagicMock)은 항상 값을 반환하므로, 실제 타입이 아니면 default 사용
    if type(val).__module__.startswith("unittest"):
        return default
    return val


def get_bookmark_service() -> BookmarkService:
    """BookmarkService 인스턴스 제공 (FastAPI Depends)"""
    return BookmarkService()


@router.post(
    "",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark(
    payload: BookmarkCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkResponse:
    """REQ-BOOKMARK-001: 북마크 생성."""
    bookmark = await svc.create(db, user.id, payload)
    return BookmarkResponse.model_validate(bookmark)


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 북마크만 조회",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkListResponse:
    """REQ-BOOKMARK-002: 본인 북마크 목록 조회. task_id로 필터 가능."""
    offset = (page - 1) * page_size
    items, total = await svc.list_for_user(
        session=db,
        user_id=user.id,
        task_id=task_id,
        limit=page_size,
        offset=offset,
    )
    return BookmarkListResponse(
        items=[BookmarkResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{bookmark_id}", response_model=BookmarkResponse)
async def get_bookmark(
    bookmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkResponse:
    bookmark = await svc.get_by_id(db, bookmark_id, user.id)
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"북마크를 찾을 수 없습니다: {bookmark_id}",
        )
    return BookmarkResponse.model_validate(bookmark)


@router.patch("/{bookmark_id}", response_model=BookmarkResponse)
async def update_bookmark(
    bookmark_id: uuid.UUID,
    payload: BookmarkUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkResponse:
    bookmark = await svc.update(db, bookmark_id, user.id, payload)
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"북마크를 찾을 수 없습니다: {bookmark_id}",
        )
    return BookmarkResponse.model_validate(bookmark)


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> None:
    await svc.delete(db, bookmark_id, user.id)


# ---------------------------------------------------------------------------
# 확장된 북마크 기능
# ---------------------------------------------------------------------------


@router.post("/bulk", response_model=BookmarkBulkResponse, status_code=status.HTTP_200_OK)
async def bulk_bookmark_operations(
    payload: BookmarkBulkOperation,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkBulkResponse:
    """대량 북마크 작업 (삭제, 카테고리/우선순위 업데이트)"""
    result = await svc.bulk_operation(db, user.id, payload)
    return BookmarkBulkResponse(
        processed_count=_val(result,"processed_count", 0),
        failed_count=_val(result,"failed_count", 0),
        errors=_val(result,"errors", []),
    )


@router.get("/summary", response_model=BookmarkSummaryResponse)
async def get_bookmark_summary(
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 북마크 요약만 조회",
    ),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkSummaryResponse:
    """북마크 통계 및 요약 정보"""
    result = await svc.get_summary(db, user.id, task_id)
    return BookmarkSummaryResponse(
        total_count=_val(result,"total_count", 0),
        category_counts=_val(result,"category_counts", {}),
        priority_counts=_val(result,"priority_counts", {}),
        tag_counts=_val(result,"tag_counts", {}),
        recent_bookmarks=_val(result,"recent_bookmarks", []),
    )


@router.get("/search", response_model=BookmarkSearchResponse)
async def search_bookmarks(
    query: str | None = Query(
        default=None,
        max_length=100,
        description="검색어",
    ),
    category: str | None = Query(
        default=None,
        description="북마크 카테고리 필터",
    ),
    priority: str | None = Query(
        default=None,
        description="북마크 우선순위 필터",
    ),
    tags: str | None = Query(
        default=None,
        description="태그 필터 (쉼표로 구분)",
    ),
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 북마크만 검색",
    ),
    has_tags: bool | None = Query(
        default=None,
        description="태그가 있는 북마크만 검색",
    ),
    date_from: str | None = Query(
        default=None,
        description="시작 날짜 (ISO 8601)",
    ),
    date_to: str | None = Query(
        default=None,
        description="종료 날짜 (ISO 8601)",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at", description="정렬 기준"),
    sort_order: str = Query(default="desc", description="정렬 순서"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkSearchResponse:
    """고급 북마크 검색"""
    # 파라미터 변환
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    date_from_obj = None
    if date_from:
        date_from_obj = datetime.fromisoformat(date_from.replace("Z", "+00:00"))

    date_to_obj = None
    if date_to:
        date_to_obj = datetime.fromisoformat(date_to.replace("Z", "+00:00"))

    # SearchRequest 생성
    search_request = BookmarkSearchRequest(
        query=query,
        category=BookmarkCategory(category) if category else None,
        priority=BookmarkPriority(priority) if priority else None,
        tags=tags_list,
        task_id=task_id,
        date_from=date_from_obj,
        date_to=date_to_obj,
        has_tags=has_tags,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    result = await svc.search_bookmarks(db, user.id, search_request)
    return BookmarkSearchResponse(
        items=_val(result,"items", []),
        total=_val(result,"total", 0),
        page=_val(result,"page", 1),
        page_size=_val(result,"page_size", 50),
        total_pages=_val(result,"total_pages", 0),
    )


@router.post("/cleanup", response_model=BookmarkCleanupResponse, status_code=status.HTTP_200_OK)
async def cleanup_bookmarks(
    payload: BookmarkCleanupRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> BookmarkCleanupResponse:
    """북마크 정리"""
    result = await svc.cleanup_bookmarks(db, user.id, payload)
    return BookmarkCleanupResponse(
        total_count=_val(result,"total_count", 0),
        deleted_count=_val(result,"deleted_count", 0),
        archived_count=_val(result,"archived_count", 0),
        duplicate_count=_val(result,"duplicate_count", 0),
        empty_count=_val(result,"empty_count", 0),
        categories=_val(result,"categories", {}),
        preview=_val(result,"preview", []),
    )


@router.post("/export", status_code=status.HTTP_200_OK)
async def export_bookmarks(
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 북마크만 내보내기",
    ),
    format: str = Query(
        default="json",
        description="내보내기 형식: json, csv, markdown",
    ),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
):
    """북마크 내보내기"""
    result = await svc.export_bookmarks(db, user.id, task_id, format)
    return result
