"""
AI 요약 API 엔드포인트
REQ-SUM-006: POST /api/v1/summaries → 202 Accepted
REQ-SUM-012: GET /api/v1/summaries/{task_id}/status → 상태 조회
REQ-SUM-013: GET /api/v1/summaries/{task_id} → 전체 결과 조회
REQ-SUM-014: Redis 결과 캐싱 24h TTL
REQ-SUM-015: DELETE /api/v1/summaries/{task_id} → 204 No Content
REQ-SUM-016: 존재하지 않는 task_id → 404
"""

import json
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.schemas.summary import (
    ActionItem,
    SummaryCreateRequest,
    SummaryResponse,
    SummaryStatusResponse,
)
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        429: {"description": "동시 처리 한도 초과"},
    },
)
async def create_summary(
    request: SummaryCreateRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    """
    AI 요약 생성 작업 요청
    POST /api/v1/summaries
    """
    # --- 동시 처리 제한 확인 (REQ-SUM-008: 최대 2개) ---
    active_count = await redis_client.scard("active_sum_jobs") or 0
    if active_count >= settings.max_concurrent_summaries:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"동시 요약 작업 한도({settings.max_concurrent_summaries}개)를 "
                "초과했습니다. 잠시 후 재시도하세요."
            ),
        )

    # --- 작업 ID 생성 및 초기 상태 저장 ---
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    initial_status = {
        "task_id": task_id,
        "minutes_task_id": request.minutes_task_id,
        "status": TaskStatus.pending.value,
        "progress": 0.0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
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


@router.get(
    "/{task_id}/status",
    response_model=SummaryStatusResponse,
    responses={404: {"description": "작업 없음"}},
)
async def get_summary_status(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> SummaryStatusResponse:
    """
    요약 작업 상태 조회
    GET /api/v1/summaries/{task_id}/status
    """
    status_key = f"task:sum:status:{task_id}"
    raw = await redis_client.get(status_key)

    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="요약 작업을 찾을 수 없습니다.",
        )

    data = json.loads(raw)

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
    redis_client: aioredis.Redis = Depends(get_redis_client),
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="요약 작업을 찾을 수 없습니다.",
            )

        status_data = json.loads(status_raw)
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
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    """
    요약 작업 및 결과 삭제
    DELETE /api/v1/summaries/{task_id}
    """
    # Redis 캐시 삭제 (상태 + 결과)
    await redis_client.delete(
        f"task:sum:status:{task_id}",
        f"task:sum:result:{task_id}",
    )

    logger.info("요약 작업 삭제", task_id=task_id)
