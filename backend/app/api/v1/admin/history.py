"""
SPEC-HISTORY-001: 작업 이력 조회/삭제 API

엔드포인트:
- GET  /history           - 페이지네이션 목록 조회 (REQ-HIST-001~004)
- GET  /history/{task_id} - 단건 상세 조회 (REQ-HIST-005~006)
- DELETE /history/{task_id} - 삭제 (REQ-HIST-007)
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.app.errors import not_found
from backend.db.auth_models import MeetingOwnership
from backend.db.models import TaskResult
from backend.db.service import ResultService
from backend.schemas.history import HistoryDetailItem, HistoryItem, HistoryListResponse

router = APIRouter(tags=["history"])


def get_result_service() -> ResultService:
    """ResultService 인스턴스 제공 (FastAPI Depends)"""
    return ResultService()


async def _shared_team_ids_by_task(
    db: AsyncSession,
    task_ids: list[str],
) -> dict[str, list[str]]:
    if not task_ids:
        return {}

    result = await db.execute(
        select(MeetingOwnership.task_id, MeetingOwnership.team_id).where(
            MeetingOwnership.task_id.in_(task_ids),
            MeetingOwnership.team_id.is_not(None),
        )
    )
    shared_by_task: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    for task_id, team_id in result.all():
        if team_id is not None:
            shared_by_task.setdefault(task_id, []).append(str(team_id))
    return shared_by_task


def _history_item(
    record: TaskResult,
    shared_by_task: dict[str, list[str]],
) -> HistoryItem:
    return HistoryItem.model_validate(record).model_copy(
        update={
            "shared_team_ids": shared_by_task.get(record.task_id, []),
            "source_task_id": _source_task_id(record),
        }
    )


def _history_detail_item(
    record: TaskResult,
    shared_by_task: dict[str, list[str]],
) -> HistoryDetailItem:
    return HistoryDetailItem.model_validate(record).model_copy(
        update={
            "shared_team_ids": shared_by_task.get(record.task_id, []),
            "source_task_id": _source_task_id(record),
        }
    )


def _source_task_id(record: TaskResult) -> str | None:
    metadata = record.input_metadata if isinstance(record.input_metadata, dict) else {}
    result_data = record.result_data if isinstance(record.result_data, dict) else {}
    for key in (
        "source_task_id",
        "minutes_task_id",
        "diarization_task_id",
        "stt_task_id",
        "transcription_task_id",
    ):
        value = metadata.get(key) or result_data.get(key)
        if value:
            return str(value)
    return None


@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    request: Request,
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
    svc: ResultService = Depends(get_result_service),
) -> HistoryListResponse:
    """
    REQ-HIST-001: 작업 이력 페이지네이션 목록 조회

    task_type, status 파라미터로 필터링할 수 있습니다.
    응답에는 result_data가 제외됩니다 (목록 응답 크기 최소화).
    """
    # offset 계산 (1-based page → 0-based offset)
    offset = (page - 1) * page_size
    owner_id = _request_owner_id(request)
    guest_session_id = _request_guest_session_id(request)

    # 전체 건수 및 목록 병렬 조회
    total = await svc.count_results(
        session=db,
        task_type=task_type,
        status=status,
        owner_id=owner_id,
        guest_session_id=guest_session_id,
    )

    records = await svc.list_results(
        session=db,
        task_type=task_type,
        status=status,
        limit=page_size,
        offset=offset,
        owner_id=owner_id,
        guest_session_id=guest_session_id,
    )

    shared_by_task = await _shared_team_ids_by_task(db, [r.task_id for r in records])
    items = [_history_item(r, shared_by_task) for r in records]

    return HistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history/{task_id}", response_model=HistoryDetailItem)
async def get_history(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    svc: ResultService = Depends(get_result_service),
) -> HistoryDetailItem:
    """
    REQ-HIST-005: task_id로 작업 이력 상세 조회

    result_data, input_metadata를 포함한 전체 정보를 반환합니다.
    REQ-HIST-006: 존재하지 않는 task_id 요청 시 404 반환
    """
    record = await svc.get_result(session=db, task_id=task_id)

    if record is None:
        not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")

    owner_id = _request_owner_id(request)
    if owner_id is not None and not await _is_owned_by(db, task_id, owner_id):
        not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")
    guest_session_id = _request_guest_session_id(request)
    if guest_session_id is not None and not _is_guest_owned(record, guest_session_id):
        not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")

    shared_by_task = await _shared_team_ids_by_task(db, [record.task_id])
    return _history_detail_item(record, shared_by_task)


@router.delete("/history/{task_id}", status_code=204)
async def delete_history(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    svc: ResultService = Depends(get_result_service),
) -> None:
    """
    REQ-HIST-007: task_id로 작업 이력 삭제

    삭제 성공 시 204 No Content를 반환합니다.
    존재하지 않는 task_id 요청 시 404를 반환합니다.
    """
    owner_id = _request_owner_id(request)
    if owner_id is not None and not await _is_owned_by(db, task_id, owner_id):
        not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")
    guest_session_id = _request_guest_session_id(request)
    if guest_session_id is not None:
        record = await svc.get_result(session=db, task_id=task_id)
        if record is None or not _is_guest_owned(record, guest_session_id):
            not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")

    deleted = await svc.delete_result(session=db, task_id=task_id)

    if not deleted:
        not_found(f"작업 이력을 찾을 수 없습니다: task_id={task_id}")


def _request_owner_id(request: Request) -> uuid.UUID | None:
    raw_user_id = getattr(request.state, "user_id", None)
    if not raw_user_id:
        return None
    try:
        return uuid.UUID(str(raw_user_id))
    except ValueError:
        return None


def _request_guest_session_id(request: Request) -> str | None:
    if getattr(request.state, "is_guest", False) is not True:
        return None
    guest_session_id = getattr(request.state, "guest_session_id", None)
    return str(guest_session_id) if guest_session_id else None


def _is_guest_owned(record: TaskResult, guest_session_id: str) -> bool:
    return bool(record.is_guest and record.guest_session_id == guest_session_id)


async def _is_owned_by(db: AsyncSession, task_id: str, owner_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(MeetingOwnership.id).where(
            MeetingOwnership.task_id == task_id,
            MeetingOwnership.owner_id == owner_id,
            MeetingOwnership.team_id.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None
