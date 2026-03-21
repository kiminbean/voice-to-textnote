"""
SPEC-HISTORY-001: 작업 이력 조회/삭제 API

엔드포인트:
- GET  /history           - 페이지네이션 목록 조회 (REQ-HIST-001~004)
- GET  /history/{task_id} - 단건 상세 조회 (REQ-HIST-005~006)
- DELETE /history/{task_id} - 삭제 (REQ-HIST-007)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.db.service import ResultService
from backend.schemas.history import HistoryDetailItem, HistoryItem, HistoryListResponse

router = APIRouter(tags=["history"])

# ResultService 인스턴스 (재사용)
_service = ResultService()


@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    task_type: str | None = Query(
        default=None,
        description="작업 유형 필터 (stt, diarization, minutes, summary)",
    ),
    status: str | None = Query(
        default=None,
        description="작업 상태 필터 (completed, failed, processing)",
    ),
    page: int = Query(default=1, ge=1, description="페이지 번호 (1부터 시작)"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지당 항목 수"),
    db: AsyncSession = Depends(get_db_session),
) -> HistoryListResponse:
    """
    REQ-HIST-001: 작업 이력 페이지네이션 목록 조회

    task_type, status 파라미터로 필터링할 수 있습니다.
    응답에는 result_data가 제외됩니다 (목록 응답 크기 최소화).
    """
    # offset 계산 (1-based page → 0-based offset)
    offset = (page - 1) * page_size

    # 전체 건수 및 목록 병렬 조회
    total = await _service.count_results(
        session=db,
        task_type=task_type,
        status=status,
    )

    records = await _service.list_results(
        session=db,
        task_type=task_type,
        status=status,
        limit=page_size,
        offset=offset,
    )

    items = [HistoryItem.model_validate(r) for r in records]

    return HistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history/{task_id}", response_model=HistoryDetailItem)
async def get_history(
    task_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> HistoryDetailItem:
    """
    REQ-HIST-005: task_id로 작업 이력 상세 조회

    result_data, input_metadata를 포함한 전체 정보를 반환합니다.
    REQ-HIST-006: 존재하지 않는 task_id 요청 시 404 반환
    """
    record = await _service.get_result(session=db, task_id=task_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"작업 이력을 찾을 수 없습니다: task_id={task_id}",
        )

    return HistoryDetailItem.model_validate(record)


@router.delete("/history/{task_id}", status_code=204)
async def delete_history(
    task_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    REQ-HIST-007: task_id로 작업 이력 삭제

    삭제 성공 시 204 No Content를 반환합니다.
    존재하지 않는 task_id 요청 시 404를 반환합니다.
    """
    deleted = await _service.delete_result(session=db, task_id=task_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"작업 이력을 찾을 수 없습니다: task_id={task_id}",
        )
