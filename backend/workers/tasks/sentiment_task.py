"""
Celery 감정 분석 작업
SPEC-SENTIMENT-001: 회의록 완료 후 화자별/구간별 감정 분석
"""

import json
import time
from datetime import UTC, datetime
from typing import cast

import redis

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.pipeline.sentiment_analyzer import SentimentAnalyzer
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app
from backend.workers.redis_client import get_worker_redis
from backend.workers.tasks.status_context import merge_existing_status_context

logger = get_logger(__name__)


def _get_redis() -> redis.Redis:
    """Redis 클라이언트 (공유 연결 풀)"""
    return get_worker_redis()


def _update_task_status(
    task_id: str,
    status: TaskStatus,
    progress: float = 0.0,
    message: str | None = None,
    error_message: str | None = None,
) -> None:
    r = _get_redis()
    status_key = f"task:sentiment:status:{task_id}"

    existing_raw = r.get(status_key)

    data: dict = {
        "task_id": task_id,
        "status": status.value,
        "progress": progress,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    data = merge_existing_status_context(existing_raw, data)
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


def _cache_result(task_id: str, result: dict) -> None:
    r = _get_redis()
    result_key = f"task:sentiment:result:{task_id}"
    r.setex(result_key, settings.summary_result_ttl, json.dumps(result))


def _load_minutes_result(minutes_task_id: str) -> dict | None:
    r = _get_redis()
    min_result_key = f"task:min:result:{minutes_task_id}"
    min_result_raw = r.get(min_result_key)
    if min_result_raw is not None:
        return json.loads(cast(str | bytes | bytearray, min_result_raw))

    try:
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session

        with get_sync_session() as session:
            stmt = select(TaskResult).where(
                TaskResult.task_id == minutes_task_id,
                TaskResult.task_type == "minutes",
                TaskResult.status == TaskStatus.completed.value,
            )
            record = session.scalars(stmt).first()
            if record is None or not isinstance(record.result_data, dict):
                return None
            minutes_data = dict(record.result_data)
            minutes_data.setdefault("task_id", minutes_task_id)
            minutes_data.setdefault("status", TaskStatus.completed.value)
            r.setex(min_result_key, settings.minutes_result_ttl, json.dumps(minutes_data))
            return minutes_data
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "감정 분석 minutes DB fallback 실패",
            minutes_task_id=minutes_task_id,
            error=str(exc),
        )
        return None


def _get_active_sentiment_count() -> int:
    """현재 활성 감정 분석 작업 수 조회 (고아 항목 자동 정리)"""
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_sentiment_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_sentiment_jobs_ts")
    return pipe.execute()[1]


def _register_active_job(task_id: str) -> None:
    r = _get_redis()
    r.zadd("active_sentiment_jobs_ts", {task_id: time.time()})


def _unregister_active_job(task_id: str) -> None:
    r = _get_redis()
    r.zrem("active_sentiment_jobs_ts", task_id)


def sentiment_task(
    task_id: str,
    minutes_task_id: str,
    max_tokens: int = 4096,
) -> dict:
    """감정 분석 메인 처리 함수"""
    processing_start = datetime.now(UTC)
    logger.info("감정 분석 작업 시작", task_id=task_id, minutes_task_id=minutes_task_id)

    # API 키 확인
    if not settings.llm_api_key:
        error_msg = "LLM API key is not configured"
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    # 동시 작업 수 제한 (REQ-SEN-004: settings.max_concurrent_sentiment 사용)
    active_count = _get_active_sentiment_count()
    if active_count >= settings.max_concurrent_sentiment:
        error_msg = (
            f"동시 감정 분석 작업 한도({settings.max_concurrent_sentiment}개)를 초과했습니다."
        )
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "rejected",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    _register_active_job(task_id)

    try:
        _update_task_status(task_id, TaskStatus.processing, 0.1, "회의록 결과 조회 중...")

        min_result = _load_minutes_result(minutes_task_id)
        if min_result is None:
            raise FileNotFoundError(
                f"회의록 결과를 찾을 수 없습니다: minutes_task_id={minutes_task_id}"
            )

        min_status = min_result.get("status")
        if min_status and min_status != TaskStatus.completed.value:
            upstream_error = min_result.get("error_message") or (
                f"회의록 작업이 완료되지 않았습니다: status={min_status}"
            )
            raise RuntimeError(
                f"회의록 생성 실패로 감정 분석을 시작할 수 없습니다: {upstream_error}"
            )

        segments = min_result.get("segments", [])
        speaker_stats = min_result.get("speakers", [])

        _update_task_status(task_id, TaskStatus.processing, 0.3, "감정 분석 생성 중...")

        # 감정 분석 수행
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze(
            segments=segments,
            speaker_stats=speaker_stats,
            api_key=settings.llm_api_key,
            model=settings.summary_model,
            max_tokens=max_tokens,
            base_url=settings.llm_base_url,
        )

        _update_task_status(task_id, TaskStatus.processing, 0.9, "결과 저장 중...")

        processing_end = datetime.now(UTC)
        generation_time = (processing_end - processing_start).total_seconds()

        final_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": TaskStatus.completed.value,
            "overall_sentiment": result.overall_sentiment,
            "overall_emotion": result.overall_emotion,
            "segments": [seg.model_dump() for seg in result.segments],
            "speakers": [sp.model_dump() for sp in result.speakers],
            "emotional_timeline": result.emotional_timeline,
            "generation_time_seconds": generation_time,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)

        # DB 영속 저장 (best-effort)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="sentiment",
                status="completed",
                result_data=final_result,
            )
        except Exception:  # pragma: no cover
            logger.warning("DB 결과 저장 실패 - Redis 캐시로 폴백", task_id=task_id, exc_info=True, category="db_fallback")

        _update_task_status(task_id, TaskStatus.completed, 1.0, "감정 분석 완료")

        logger.info("감정 분석 완료", task_id=task_id, generation_time=generation_time)
        return final_result

    except FileNotFoundError as exc:
        error_msg = str(exc)
        logger.error("감정 분석 실패 (회의록 결과 없음)", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("감정 분석 실패", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    finally:
        _unregister_active_job(task_id)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="sentiment_task",
)
def sentiment_celery_task(
    self,
    task_id: str,
    minutes_task_id: str,
    max_tokens: int = 4096,
) -> dict:
    """Celery 래퍼: 감정 분석 + 재시도 처리"""
    try:
        return sentiment_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            max_tokens=max_tokens,
        )
    except FileNotFoundError as exc:
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("감정 분석 최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}
