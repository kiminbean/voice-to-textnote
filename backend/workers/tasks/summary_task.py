"""
Celery AI 요약 생성 작업
REQ-SUM-006: POST /api/v1/summaries → Celery 비동기 처리
REQ-SUM-007: Redis에서 회의록 결과 조회 (task:min:result:{minutes_task_id})
REQ-SUM-008: 최대 2개 동시 작업 제한
REQ-SUM-009: 최대 2회 재시도, default_retry_delay=30s
REQ-SUM-010: 회의록 결과 없음 → 즉시 실패 (재시도 없음)
REQ-SUM-011: ANTHROPIC_API_KEY 빈 값 → 즉시 실패 (재시도 없음)
REQ-SUM-014: Redis 결과 캐싱 24h TTL (task:sum:result:{task_id})
"""

import json
from datetime import UTC, datetime

import redis

from backend.app.config import settings
from backend.pipeline.summary_generator import SummaryGenerator
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app

logger = get_logger(__name__)

# Redis 동기 클라이언트 (Celery 워커는 동기 환경)
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    """Redis 클라이언트 싱글톤 반환"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _update_task_status(
    task_id: str,
    status: TaskStatus,
    progress: float = 0.0,
    message: str | None = None,
    error_message: str | None = None,
) -> None:
    """Redis에 요약 작업 상태 업데이트"""
    r = _get_redis()
    data: dict = {
        "task_id": task_id,
        "status": status.value,
        "progress": progress,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if message:
        data["message"] = message
    if error_message:
        data["error_message"] = error_message

    status_key = f"task:sum:status:{task_id}"
    r.setex(status_key, settings.summary_result_ttl, json.dumps(data))


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 요약 결과 캐싱 (REQ-SUM-014: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:sum:result:{task_id}"
    r.setex(result_key, settings.summary_result_ttl, json.dumps(result))


def _get_active_sum_count() -> int:
    """현재 활성 요약 작업 수 조회"""
    r = _get_redis()
    return r.scard("active_sum_jobs") or 0


def _register_active_job(task_id: str) -> None:
    """활성 작업 등록"""
    r = _get_redis()
    r.sadd("active_sum_jobs", task_id)


def _unregister_active_job(task_id: str) -> None:
    """활성 작업 해제"""
    r = _get_redis()
    r.srem("active_sum_jobs", task_id)


def summary_task(
    task_id: str,
    minutes_task_id: str,
    max_tokens: int = 2000,
) -> dict:
    """
    메인 AI 요약 생성 처리 함수 (Celery 워커에서 호출)

    Args:
        task_id: 요약 작업 UUID
        minutes_task_id: 회의록 작업 UUID (결과 조회용)
        max_tokens: Claude API 최대 응답 토큰 수

    Returns:
        완료 또는 실패 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    logger.info("요약 생성 작업 시작", task_id=task_id, minutes_task_id=minutes_task_id)

    # --- API 키 확인 (REQ-SUM-011: 빈 값이면 즉시 실패, 재시도 없음) ---
    if not settings.anthropic_api_key:
        error_msg = "ANTHROPIC_API_KEY is not configured"
        logger.error("API 키 미설정으로 요약 작업 실패", task_id=task_id)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    # --- 동시 작업 수 제한 확인 (REQ-SUM-008: 최대 2개) ---
    active_count = _get_active_sum_count()
    if active_count >= settings.max_concurrent_summaries:
        error_msg = (
            f"동시 요약 작업 한도({settings.max_concurrent_summaries}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )
        logger.warning("요약 작업 한도 초과", task_id=task_id, active_count=active_count)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "rejected",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    # 활성 작업 등록
    _register_active_job(task_id)

    try:
        _update_task_status(task_id, TaskStatus.processing, 0.1, "회의록 결과 조회 중...")

        # --- 1단계: 회의록 결과 조회 (REQ-SUM-007) ---
        r = _get_redis()
        min_result_key = f"task:min:result:{minutes_task_id}"
        min_result_raw = r.get(min_result_key)

        if min_result_raw is None:
            # 회의록 결과 없음 → 즉시 실패 (REQ-SUM-010: 재시도 없음)
            raise FileNotFoundError(
                f"회의록 결과를 찾을 수 없습니다: minutes_task_id={minutes_task_id}"
            )

        min_result = json.loads(min_result_raw)
        segments = min_result.get("segments", [])
        speaker_stats = min_result.get("speakers", [])

        _update_task_status(task_id, TaskStatus.processing, 0.3, "AI 요약 생성 중...")

        # --- 2단계: SummaryGenerator로 요약 생성 ---
        generator = SummaryGenerator()
        summary_result = generator.generate_summary(
            segments=segments,
            speaker_stats=speaker_stats,
            api_key=settings.anthropic_api_key,
            model=settings.summary_model,
            max_tokens=max_tokens,
        )

        _update_task_status(task_id, TaskStatus.processing, 0.9, "결과 저장 중...")

        processing_end = datetime.now(UTC)
        generation_time = (processing_end - processing_start).total_seconds()

        # --- 3단계: 결과 저장 ---
        final_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": TaskStatus.completed.value,
            "summary_text": summary_result.summary_text,
            "action_items": [item.model_dump() for item in summary_result.action_items],
            "key_decisions": summary_result.key_decisions,
            "next_steps": summary_result.next_steps,
            "generation_time_seconds": generation_time,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)
        _update_task_status(task_id, TaskStatus.completed, 1.0, "요약 생성 완료")

        logger.info(
            "요약 생성 완료",
            task_id=task_id,
            generation_time=generation_time,
        )
        return final_result

    except FileNotFoundError as exc:
        # 회의록 결과 없음 → 즉시 실패 (REQ-SUM-010: 재시도 없음)
        error_msg = str(exc)
        logger.error("요약 생성 실패 (회의록 결과 없음)", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("요약 생성 실패", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "minutes_task_id": minutes_task_id,
            "status": "failed",
            "error": error_msg,
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
    name="summary_task",
)
def summary_celery_task(
    self,
    task_id: str,
    minutes_task_id: str,
    max_tokens: int = 2000,
) -> dict:
    """
    Celery 래퍼: summary_task 호출 + 재시도 처리 (REQ-SUM-009)

    Args:
        task_id: 요약 작업 UUID
        minutes_task_id: 회의록 작업 UUID
        max_tokens: Claude API 최대 응답 토큰
    """
    try:
        return summary_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            max_tokens=max_tokens,
        )
    except FileNotFoundError as exc:
        # 회의록 결과 없음 → 재시도 안 함 (REQ-SUM-010)
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        # 일반 오류 → 재시도 (최대 2회, delay=30s) (REQ-SUM-009)
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}
