"""
Celery AI 마인드맵 생성 작업.
완료된 요약 결과(task:sum:result:{summary_task_id})를 입력으로 관계 추론형 그래프를 생성한다.
"""

import json
from datetime import UTC, datetime
from typing import cast

import redis

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.pipeline.mind_map_generator import MindMapGenerator
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app
from backend.workers.redis_client import get_worker_redis

logger = get_logger(__name__)


def _get_redis() -> redis.Redis:
    """Redis 클라이언트 (공유 연결 풀)"""
    return get_worker_redis()


def _update_mind_map_status(
    task_id: str,
    summary_task_id: str,
    status: TaskStatus,
    progress: float = 0.0,
    message: str | None = None,
    error_message: str | None = None,
) -> None:
    """Redis에 마인드맵 작업 상태 업데이트 + Pub/Sub 이벤트 발행"""
    r = _get_redis()
    status_key = f"task:mind:status:{task_id}"

    existing_created_at = None
    existing_raw = r.get(status_key)
    if existing_raw:
        existing_data = json.loads(cast(str | bytes | bytearray, existing_raw))
        existing_created_at = existing_data.get("created_at")

    data: dict = {
        "task_id": task_id,
        "summary_task_id": summary_task_id,
        "status": status.value,
        "progress": progress,
        "task_type": "mind_map",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if existing_created_at:
        data["created_at"] = existing_created_at
    if message:
        data["message"] = message
    if error_message:
        data["error_message"] = error_message

    r.setex(status_key, settings.summary_result_ttl, json.dumps(data))

    event_type = (
        "completed"
        if status == TaskStatus.completed
        else ("failed" if status == TaskStatus.failed else "status_update")
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_mind_map_result(task_id: str, result: dict) -> None:
    r = _get_redis()
    r.setex(f"task:mind:result:{task_id}", settings.summary_result_ttl, json.dumps(result))


def mind_map_task(task_id: str, summary_task_id: str, max_tokens: int = 2048) -> dict:
    """
    마인드맵 생성 처리 함수.

    Args:
        task_id: 마인드맵 작업 UUID
        summary_task_id: 완료된 요약 작업 UUID
        max_tokens: OpenAI API 최대 응답 토큰 수
    """
    processing_start = datetime.now(UTC)
    logger.info("마인드맵 생성 작업 시작", task_id=task_id, summary_task_id=summary_task_id)

    if not settings.llm_api_key:
        error_msg = "LLM API key is not configured"
        _update_mind_map_status(
            task_id,
            summary_task_id,
            TaskStatus.failed,
            0.0,
            error_message=error_msg,
        )
        failed_result = _failed_result(task_id, summary_task_id, error_msg, processing_start)
        _cache_mind_map_result(task_id, failed_result)
        return failed_result

    try:
        _update_mind_map_status(
            task_id,
            summary_task_id,
            TaskStatus.processing,
            0.2,
            "요약 결과 조회 중...",
        )

        r = _get_redis()
        summary_raw = r.get(f"task:sum:result:{summary_task_id}")
        if summary_raw is None:
            raise FileNotFoundError(
                f"요약 결과를 찾을 수 없습니다: summary_task_id={summary_task_id}"
            )

        summary_data = json.loads(cast(str | bytes | bytearray, summary_raw))
        summary_status = summary_data.get("status")
        if summary_status != TaskStatus.completed.value:
            upstream_error = (
                summary_data.get("error_message")
                or summary_data.get("error")
                or f"요약 작업이 완료되지 않았습니다: status={summary_status}"
            )
            raise RuntimeError(f"요약 결과가 완료 상태가 아닙니다: {upstream_error}")

        _update_mind_map_status(
            task_id,
            summary_task_id,
            TaskStatus.processing,
            0.5,
            "AI 마인드맵 생성 중...",
        )

        generator = MindMapGenerator()
        root, edges = generator.generate_mind_map(
            summary_data=summary_data,
            api_key=settings.llm_api_key,
            model=settings.summary_model,
            max_tokens=max_tokens,
            base_url=settings.llm_base_url,
        )

        processing_end = datetime.now(UTC)
        generation_time = (processing_end - processing_start).total_seconds()
        final_result = {
            "task_id": task_id,
            "summary_task_id": summary_task_id,
            "status": TaskStatus.completed.value,
            "root": root.model_dump(),
            "edges": [edge.model_dump() for edge in edges],
            "generation_time_seconds": generation_time,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_mind_map_result(task_id, final_result)
        _update_mind_map_status(
            task_id,
            summary_task_id,
            TaskStatus.completed,
            1.0,
            "마인드맵 생성 완료",
        )

        logger.info("마인드맵 생성 완료", task_id=task_id, generation_time=generation_time)
        return final_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("마인드맵 생성 실패", task_id=task_id, error=error_msg)
        _update_mind_map_status(
            task_id,
            summary_task_id,
            TaskStatus.failed,
            0.0,
            error_message=error_msg,
        )
        failed_result = _failed_result(task_id, summary_task_id, error_msg, processing_start)
        _cache_mind_map_result(task_id, failed_result)
        return failed_result


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="mind_map_task",
)
def mind_map_celery_task(
    self,
    task_id: str,
    summary_task_id: str,
    max_tokens: int = 2048,
) -> dict:
    """Celery 래퍼: mind_map_task 호출 + 재시도 처리."""
    try:
        return mind_map_task(
            task_id=task_id,
            summary_task_id=summary_task_id,
            max_tokens=max_tokens,
        )
    except FileNotFoundError as exc:
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("마인드맵 최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}


def _failed_result(
    task_id: str,
    summary_task_id: str,
    error_msg: str,
    created_at: datetime,
) -> dict:
    return {
        "task_id": task_id,
        "summary_task_id": summary_task_id,
        "status": TaskStatus.failed.value,
        "error": error_msg,
        "error_message": error_msg,
        "created_at": created_at.isoformat(),
    }
