"""
SPEC-BOOKMARK-001: 회의록 북마크/하이라이트 API

엔드포인트 (모두 JWT 인증 필요):
- POST   /api/v1/bookmarks              생성
- GET    /api/v1/bookmarks               목록 (task_id 필터링 지원)
- GET    /api/v1/bookmarks/{bookmark_id} 단건 조회
- PATCH  /api/v1/bookmarks/{bookmark_id} 부분 수정
- DELETE /api/v1/bookmarks/{bookmark_id} 삭제
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.services.bookmark_service import BookmarkService
from backend.schemas.bookmark import (
    BookmarkCreate,
    BookmarkListResponse,
    BookmarkResponse,
    BookmarkUpdate,
)

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


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
    return BookmarkResponse.model_validate(bookmark)


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    bookmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: BookmarkService = Depends(get_bookmark_service),
) -> None:
    await svc.delete(db, bookmark_id, user.id)
