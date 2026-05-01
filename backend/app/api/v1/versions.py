"""
회의록 버전 관리 API 엔드포인트
SPEC-VERSION-001: 버전 스냅샷 저장/조회/비교/삭제
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.db.version_models import MinutesVersion
from backend.db.version_service import VersionService
from backend.schemas.version import (
    VersionCreate,
    VersionDiffResponse,
    VersionListResponse,
    VersionResponse,
)

router = APIRouter(prefix="/minutes", tags=["versions"])
_service = VersionService()


def _to_response(version: MinutesVersion) -> VersionResponse:
    return VersionResponse(
        id=version.id,
        task_id=version.task_id,
        version_number=version.version_number,
        content=version.content,
        change_summary=version.change_summary,
        author_id=version.author_id,
        created_at=version.created_at,
    )


@router.post(
    "/{task_id}/versions",
    status_code=201,
    response_model=VersionResponse,
    responses={404: {"description": "회의록 없음"}},
)
async def create_version(
    task_id: str,
    payload: VersionCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VersionResponse:
    """회의록 현재 내용을 버전 스냅샷으로 저장."""
    version = await _service.create_version(
        db, task_id, payload, author_id=current_user.id
    )
    return _to_response(version)


@router.get(
    "/{task_id}/versions",
    response_model=VersionListResponse,
    responses={404: {"description": "회의록 없음"}},
)
async def list_versions(
    task_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="페이지 크기"),
    offset: int = Query(default=0, ge=0, description="페이지 오프셋"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VersionListResponse:
    """회의록 버전 목록 조회 (최신 버전 우선)."""
    items, total = await _service.list_versions(db, task_id, limit=limit, offset=offset)
    return VersionListResponse(total=total, items=[_to_response(v) for v in items])


@router.get(
    "/{task_id}/versions/{version_id}",
    response_model=VersionResponse,
    responses={404: {"description": "버전 없음"}},
)
async def get_version(
    task_id: str,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VersionResponse:
    """특정 버전 단건 조회."""
    version = await _service.get_version(db, task_id, version_id)
    return _to_response(version)


@router.get(
    "/{task_id}/versions/{from_version_id}/diff/{to_version_id}",
    response_model=VersionDiffResponse,
    responses={404: {"description": "버전 없음"}},
)
async def get_diff(
    task_id: str,
    from_version_id: uuid.UUID,
    to_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VersionDiffResponse:
    """두 버전 간 텍스트 diff 조회."""
    from_ver = await _service.get_version(db, task_id, from_version_id)
    to_ver = await _service.get_version(db, task_id, to_version_id)
    diff = _service.compute_diff(from_ver.content, to_ver.content)

    return VersionDiffResponse(
        from_version=from_ver.version_number,
        to_version=to_ver.version_number,
        unified_diff=diff["unified_diff"],
        added_lines=diff["added_lines"],
        removed_lines=diff["removed_lines"],
        changed=diff["changed"],
    )


@router.delete(
    "/{task_id}/versions/{version_id}",
    status_code=204,
    responses={404: {"description": "버전 없음"}},
)
async def delete_version(
    task_id: str,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """버전 삭제."""
    await _service.delete_version(db, task_id, version_id)
