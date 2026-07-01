"""
SPEC-RELATED-001: 관련 회의 추천(Related Meetings) API

엔드포인트:
- GET /related-meetings/{task_id}
  기준 회의의 상위 키워드를 이용해 FTS5 인덱스에서 유사한 다른 회의를 찾는다.

기존 search_index(FTS5)와 KeywordService를 재사용하며 새로운 외부 의존성이 없다.
"""

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import (
    get_db_session,
    get_optional_current_user,
    require_task_access,
)
from backend.app.errors import unprocessable
from backend.schemas.related_meetings import RelatedMeetingsResponse
from backend.services.related_meetings_service import RelatedMeetingsService

router = APIRouter(prefix="/related-meetings", tags=["related-meetings"])


def get_related_meetings_service() -> RelatedMeetingsService:
    """RelatedMeetingsService 인스턴스 제공 (FastAPI Depends)"""
    return RelatedMeetingsService()


@router.get(
    "/{task_id}",
    response_model=RelatedMeetingsResponse,
    responses={404: {"description": "회의를 찾을 수 없거나 접근 권한 없음"}},
)
async def get_related_meetings(
    request: Request,
    task_id: str = Path(..., min_length=1, description="기준 회의 task_id"),
    limit: int | None = Query(
        default=None,
        ge=1,
        description="반환할 최대 관련 회의 수 (미지정 시 설정 기본값)",
    ),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_optional_current_user),
    svc: RelatedMeetingsService = Depends(get_related_meetings_service),
) -> RelatedMeetingsResponse:
    """
    SPEC-RELATED-001: 관련 회의 추천

    기준 회의(task_id)에서 추출한 상위 키워드로 FTS5 인덱스를 검색하여
    공유 키워드가 많은 다른 회의를 관련도 순으로 반환한다.

    - task_id: 기준 회의 task_id (접근 권한이 없으면 404)
    - limit: 반환 개수 (1 이상, 설정된 최대값으로 상한 처리)
    """
    # limit 상한 검증 (하드코딩 금지 — 설정값 사용)
    if limit is not None and limit > settings.related_meetings_max_limit:
        unprocessable(
            f"limit은 최대 {settings.related_meetings_max_limit}까지 허용됩니다."
        )

    # 접근 권한이 없는 회의는 404로 숨긴다 (다중 사용자 격리).
    await require_task_access(request=request, db=db, task_id=task_id)

    owner_id = getattr(current_user, "id", None)
    guest_session_id = (
        str(getattr(request.state, "guest_session_id", ""))
        if getattr(request.state, "is_guest", False)
        else None
    )

    return await svc.find_related(
        session=db,
        source_task_id=task_id,
        limit=limit,
        owner_id=owner_id,
        guest_session_id=guest_session_id,
    )
