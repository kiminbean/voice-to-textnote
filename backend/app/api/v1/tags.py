"""
SPEC-TAG-001: 회의록 태그 관리 API

엔드포인트:
- POST   /api/v1/tags/auto              AI 자동 태깅
- POST   /api/v1/tags                    수동 태그 생성
- GET    /api/v1/tags                    태그 목록 (task_id 필수)
- GET    /api/v1/tags/{id}               단건 조회
- PATCH  /api/v1/tags/{id}               수정
- DELETE /api/v1/tags/{id}               삭제
- DELETE /api/v1/tags/bulk               회의록 태그 일괄 삭제
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.db.tag_service import TagService
from backend.ml.tagging_engine import generate_auto_tags
from backend.schemas.tag import (
    AutoTagRequest,
    AutoTagResponse,
    TagCreate,
    TagListResponse,
    TagResponse,
    TagUpdate,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tags", tags=["tags"])

_service = TagService()


@router.post(
    "/auto",
    response_model=AutoTagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def auto_tag_meeting(
    payload: AutoTagRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> AutoTagResponse:
    """REQ-TAG-001: AI 기반 자동 태깅. 회의록 내용 분석 후 태그 자동 생성."""
    # AI 태그 추출
    raw_tags = await generate_auto_tags(payload.content, payload.max_tags)

    # DB에 저장
    tag_creates = []
    for raw in raw_tags:
        tag_creates.append(
            TagCreate(
                task_id=payload.task_id,
                tag_type=raw.get("tag_type", "topic"),
                tag_value=raw.get("tag_value", ""),
                source="auto",
                confidence=raw.get("confidence"),
            )
        )

    created = await _service.bulk_create(db, user.id, payload.task_id, tag_creates)
    tag_responses = [TagResponse.model_validate(t) for t in created]

    return AutoTagResponse(
        task_id=payload.task_id,
        tags=tag_responses,
        total=len(tag_responses),
    )


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(
    payload: TagCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TagResponse:
    """수동 태그 생성."""
    tag = await _service.create(db, user.id, payload)
    return TagResponse.model_validate(tag)


@router.get("", response_model=TagListResponse)
async def list_tags(
    task_id: str = Query(..., max_length=255, description="회의록 task_id (필수)"),
    tag_type: str | None = Query(default=None, max_length=50, description="태그 종류 필터"),
    source: str | None = Query(default=None, max_length=20, description="생성 방식 필터 (auto/manual)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TagListResponse:
    """회의록 태그 목록 조회."""
    limit = page_size
    offset = (page - 1) * page_size
    items, total = await _service.list_for_meeting(
        db, user.id, task_id, tag_type, source, limit, offset
    )
    return TagListResponse(
        items=[TagResponse.model_validate(t) for t in items],
        total=total,
        task_id=task_id,
    )


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TagResponse:
    """태그 단건 조회."""
    tag = await _service.get_by_id(db, tag_id, user.id)
    return TagResponse.model_validate(tag)


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    payload: TagUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> TagResponse:
    """태그 수정."""
    tag = await _service.update(db, tag_id, user.id, payload)
    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> None:
    """태그 삭제."""
    await _service.delete(db, tag_id, user.id)


@router.delete("/bulk/delete", status_code=status.HTTP_200_OK)
async def bulk_delete_tags(
    task_id: str = Query(..., max_length=255, description="회의록 task_id"),
    source: str | None = Query(default=None, max_length=20, description="삭제할 태그 소스 필터"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> dict:
    """회의록 태그 일괄 삭제."""
    count = await _service.delete_all_for_meeting(db, user.id, task_id, source)
    return {"deleted": count, "task_id": task_id}
