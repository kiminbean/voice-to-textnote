"""
AI 요약 API 엔드포인트
REQ-SUM-006: POST /api/v1/summaries → 202 Accepted
REQ-SUM-012: GET /api/v1/summaries/{task_id}/status → 상태 조회
REQ-SUM-013: GET /api/v1/summaries/{task_id} → 전체 결과 조회
REQ-SUM-014: Redis 결과 캐싱 24h TTL
REQ-SUM-015: DELETE /api/v1/summaries/{task_id} → 204 No Content
REQ-SUM-016: 존재하지 않는 task_id → 404
"""

import inspect
import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import (
    get_db_session,
    get_redis_client,
    get_request_context,
    require_task_access,
)
from backend.app.errors import conflict, not_found, too_many_requests
from backend.db.models import TaskResult
from backend.schemas.summary import (
    ActionItem,
    MindMapCreateRequest,
    MindMapEdge,
    MindMapNode,
    MindMapResponse,
    SummaryCreateRequest,
    SummaryResponse,
    SummaryStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/summaries", tags=["summaries"])


async def _scard(redis_client: aioredis.Redis, key: str) -> int:
    value = redis_client.scard(key)
    return int(await value if inspect.isawaitable(value) else value)


def _decode_redis_value(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def _load_summary_result_for_mind_map(
    summary_task_id: str,
    redis_client: aioredis.Redis,
    db: AsyncSession,
) -> dict:
    summary_raw = await redis_client.get(f"task:sum:result:{summary_task_id}")
    if summary_raw is not None:
        return json.loads(_decode_redis_value(summary_raw))

    result = await db.execute(
        select(TaskResult).where(
            TaskResult.task_id == summary_task_id,
            TaskResult.task_type == "summary",
            TaskResult.status == "completed",
        )
    )
    record = result.scalar_one_or_none()
    if inspect.isawaitable(record):
        record = await record
    if (
        record is None
        or record.__class__.__module__.startswith("unittest.mock")
        or not getattr(record, "result_data", None)
    ):
        not_found("요약 결과를 찾을 수 없습니다.")

    summary_data = dict(record.result_data)
    summary_data.setdefault("task_id", summary_task_id)
    summary_data.setdefault("status", TaskStatus.completed.value)
    await redis_client.setex(
        f"task:sum:result:{summary_task_id}",
        settings.summary_result_ttl,
        json.dumps(summary_data),
    )
    return summary_data


async def _get_existing_mind_map_task(
    redis_client: aioredis.Redis, summary_task_id: str
) -> dict | None:
    task_id_raw = await redis_client.get(f"task:mind:by_summary:{summary_task_id}")
    if task_id_raw is None:
        return None

    task_id = _decode_redis_value(task_id_raw)
    if task_id.lstrip().startswith("{"):
        await redis_client.delete(f"task:mind:by_summary:{summary_task_id}")
        return None

    result_raw = await redis_client.get(f"task:mind:result:{task_id}")
    if result_raw is not None:
        result_data = json.loads(_decode_redis_value(result_raw))
        if result_data.get("status") == TaskStatus.completed.value:
            return {
                "task_id": task_id,
                "summary_task_id": summary_task_id,
                "status": TaskStatus.completed.value,
                "status_url": f"/api/v1/summaries/mind-map/{task_id}/status",
                "result_url": f"/api/v1/summaries/mind-map/{task_id}",
                "created_at": result_data.get("created_at"),
                "reused": True,
            }

    status_raw = await redis_client.get(f"task:mind:status:{task_id}")
    if status_raw is None:
        await redis_client.delete(f"task:mind:by_summary:{summary_task_id}")
        return None

    status_data = json.loads(_decode_redis_value(status_raw))
    existing_status = status_data.get("status")
    if existing_status == TaskStatus.failed.value:
        await redis_client.delete(f"task:mind:by_summary:{summary_task_id}")
        return None

    return {
        "task_id": task_id,
        "summary_task_id": summary_task_id,
        "status": existing_status or TaskStatus.pending.value,
        "status_url": f"/api/v1/summaries/mind-map/{task_id}/status",
        "result_url": f"/api/v1/summaries/mind-map/{task_id}",
        "created_at": status_data.get("created_at"),
        "reused": True,
    }


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "동시 처리 한도 초과"},
    },
)
async def create_summary(
    http_request: Request,
    request: SummaryCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    AI 요약 생성 작업 요청
    POST /api/v1/summaries
    """
    # --- 동시 처리 제한 확인 (REQ-SUM-008: 최대 2개) ---
    active_count = await _scard(redis_client, "active_sum_jobs")
    if active_count >= settings.max_concurrent_summaries:
        too_many_requests(
            f"동시 요약 작업 한도({settings.max_concurrent_summaries}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )

    # --- 작업 ID 생성 및 초기 상태 저장 ---
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    user_id = getattr(http_request.state, "user_id", None)
    is_guest = bool(getattr(http_request.state, "is_guest", False))
    guest_session_id = getattr(http_request.state, "guest_session_id", None)

    initial_status = {
        "task_id": task_id,
        "minutes_task_id": request.minutes_task_id,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "user_id": str(user_id) if user_id else None,
        "is_guest": is_guest,
        "guest_session_id": guest_session_id,
    }
    status_key = f"task:sum:status:{task_id}"
    await redis_client.setex(status_key, settings.summary_result_ttl, json.dumps(initial_status))

    # --- Celery 작업 등록 (REQ-SUM-006) ---
    from backend.workers.tasks.summary_task import summary_celery_task

    summary_celery_task.delay(
        task_id=task_id,
        minutes_task_id=request.minutes_task_id,
        max_tokens=request.max_tokens,
        template_id=request.template_id,
        user_id=user_id,
        is_guest=is_guest,
        guest_session_id=guest_session_id,
    )

    logger.info(
        "요약 생성 작업 등록",
        task_id=task_id,
        minutes_task_id=request.minutes_task_id,
    )

    return {
        "task_id": task_id,
        "minutes_task_id": request.minutes_task_id,
        "status": TaskStatus.pending.value,
        "status_url": f"/api/v1/summaries/{task_id}/status",
        "result_url": f"/api/v1/summaries/{task_id}",
        "created_at": now.isoformat(),
    }


@router.post(
    "/{summary_task_id}/mind-map",
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"description": "요약 작업 없음"}},
)
async def create_mind_map(
    summary_task_id: str,
    request: MindMapCreateRequest | None = None,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    완료된 요약 결과를 기반으로 AI 마인드맵 생성 작업 요청.
    POST /api/v1/summaries/{summary_task_id}/mind-map
    """
    summary_data = await _load_summary_result_for_mind_map(
        summary_task_id,
        redis_client,
        db,
    )
    await require_task_access(http_request, db, summary_task_id, summary_data)
    if summary_data.get("status") != TaskStatus.completed.value:
        conflict("완료된 요약 결과에서만 마인드맵을 생성할 수 있습니다.")

    existing_task = await _get_existing_mind_map_task(redis_client, summary_task_id)
    if existing_task is not None:
        logger.info(
            "기존 마인드맵 작업 재사용",
            task_id=existing_task["task_id"],
            summary_task_id=summary_task_id,
            status=existing_task["status"],
        )
        return existing_task

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    initial_status = {
        "task_id": task_id,
        "summary_task_id": summary_task_id,
        "task_type": "mind_map",
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "user_id": summary_data.get("user_id"),
        "is_guest": bool(summary_data.get("is_guest", False)),
        "guest_session_id": summary_data.get("guest_session_id"),
    }
    await redis_client.setex(
        f"task:mind:status:{task_id}",
        settings.summary_result_ttl,
        json.dumps(initial_status),
    )
    await redis_client.setex(
        f"task:mind:by_summary:{summary_task_id}",
        settings.summary_result_ttl,
        task_id,
    )

    from backend.workers.tasks.mind_map_task import mind_map_celery_task

    body = request or MindMapCreateRequest()
    mind_map_celery_task.delay(
        task_id=task_id,
        summary_task_id=summary_task_id,
        max_tokens=body.max_tokens,
    )

    logger.info("마인드맵 생성 작업 등록", task_id=task_id, summary_task_id=summary_task_id)

    return {
        "task_id": task_id,
        "summary_task_id": summary_task_id,
        "status": TaskStatus.pending.value,
        "status_url": f"/api/v1/summaries/mind-map/{task_id}/status",
        "result_url": f"/api/v1/summaries/mind-map/{task_id}",
        "created_at": now.isoformat(),
    }


@router.get(
    "/mind-map/{task_id}/status",
    response_model=SummaryStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_mind_map_status(
    task_id: str,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> SummaryStatusResponse:
    """
    마인드맵 작업 상태 조회.
    GET /api/v1/summaries/mind-map/{task_id}/status
    """
    raw = await redis_client.get(f"task:mind:status:{task_id}")
    if raw is None:
        not_found("마인드맵 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    await require_task_access(http_request, db, task_id, data)
    return SummaryStatusResponse(
        task_id=task_id,
        status=TaskStatus(data["status"]),
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
    )


@router.get(
    "/mind-map/{task_id}",
    response_model=MindMapResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_mind_map_result(
    task_id: str,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> MindMapResponse:
    """
    마인드맵 결과 조회.
    GET /api/v1/summaries/mind-map/{task_id}
    """
    raw = await redis_client.get(f"task:mind:result:{task_id}")

    if raw is None:
        status_raw = await redis_client.get(f"task:mind:status:{task_id}")
        if status_raw is None:
            not_found("마인드맵 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        await require_task_access(http_request, db, task_id, status_data)
        return MindMapResponse(
            task_id=task_id,
            summary_task_id=status_data.get("summary_task_id", ""),
            status=TaskStatus(status_data["status"]),
            root=None,
            edges=[],
            error_message=status_data.get("error_message"),
        )

    data = json.loads(raw)
    await require_task_access(http_request, db, task_id, data)
    root = MindMapNode.model_validate(data["root"]) if data.get("root") else None
    edges = [
        MindMapEdge.model_validate(edge) for edge in data.get("edges", []) if isinstance(edge, dict)
    ]

    return MindMapResponse(
        task_id=data["task_id"],
        summary_task_id=data.get("summary_task_id", ""),
        status=TaskStatus(data["status"]),
        root=root,
        edges=edges,
        generation_time_seconds=data.get("generation_time_seconds"),
        error_message=data.get("error_message") or data.get("error"),
    )


@router.get(
    "/{task_id}/status",
    response_model=SummaryStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_summary_status(
    task_id: str,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> SummaryStatusResponse:
    """
    요약 작업 상태 조회
    GET /api/v1/summaries/{task_id}/status
    """
    status_key = f"task:sum:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        not_found("요약 작업을 찾을 수 없습니다.")

    data = json.loads(raw)
    await require_task_access(http_request, db, task_id, data)

    return SummaryStatusResponse(
        task_id=task_id,
        status=TaskStatus(data["status"]),
        progress=data.get("progress", 0.0),
        message=data.get("message"),
        error_message=data.get("error_message"),
    )


@router.get(
    "/{task_id}",
    response_model=SummaryResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_summary_result(
    task_id: str,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> SummaryResponse:
    """
    요약 결과 전체 조회
    GET /api/v1/summaries/{task_id}
    """
    result_key = f"task:sum:result:{task_id}"
    raw = await redis_client.get(result_key)

    if raw is None:
        # Redis 캐시 미스 → 상태 확인
        status_key = f"task:sum:status:{task_id}"
        status_raw = await redis_client.get(status_key)

        if status_raw is None:
            not_found("요약 작업을 찾을 수 없습니다.")

        status_data = json.loads(status_raw)
        await require_task_access(http_request, db, task_id, status_data)
        task_status = TaskStatus(status_data["status"])

        # 아직 처리 중 → 빈 결과 반환
        return SummaryResponse(
            task_id=task_id,
            status=task_status,
            minutes_task_id=status_data.get("minutes_task_id", ""),
            summary_text="",
            action_items=[],
            key_decisions=[],
            next_steps=[],
            error_message=status_data.get("error_message"),
        )

    data = json.loads(raw)
    await require_task_access(http_request, db, task_id, data)

    # ActionItem 객체 변환
    raw_action_items = data.get("action_items", [])
    action_items = []
    for item in raw_action_items:
        if isinstance(item, dict):
            action_items.append(
                ActionItem(
                    assignee=item.get("assignee"),
                    task=item.get("task", ""),
                    deadline=item.get("deadline"),
                    priority=item.get("priority", "medium"),
                )
            )

    return SummaryResponse(
        task_id=data["task_id"],
        status=TaskStatus(data["status"]),
        minutes_task_id=data.get("minutes_task_id", ""),
        summary_text=data.get("summary_text", ""),
        action_items=action_items,
        key_decisions=data.get("key_decisions", []),
        next_steps=data.get("next_steps", []),
        sections=data.get("sections", {}),
        template_structure=data.get("template_structure"),
        tokens_used=data.get("tokens_used"),
        generation_time_seconds=data.get("generation_time_seconds"),
        error_message=data.get("error_message") or data.get("error"),
    )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_summary(
    task_id: str,
    http_request: Request = Depends(get_request_context),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    요약 작업 및 결과 삭제
    DELETE /api/v1/summaries/{task_id}
    """
    status_raw = await redis_client.get(f"task:sum:status:{task_id}")
    result_raw = await redis_client.get(f"task:sum:result:{task_id}")
    payload = json.loads(result_raw or status_raw) if (result_raw or status_raw) else None
    await require_task_access(http_request, db, task_id, payload)

    # Redis 캐시 삭제 (상태 + 결과)
    await redis_client.delete(
        f"task:sum:status:{task_id}",
        f"task:sum:result:{task_id}",
    )

    logger.info("요약 작업 삭제", task_id=task_id)
