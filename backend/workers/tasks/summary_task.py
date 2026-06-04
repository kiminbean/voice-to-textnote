"""
Celery AI 요약 생성 작업
REQ-SUM-006: POST /api/v1/summaries → Celery 비동기 처리
REQ-SUM-007: Redis에서 회의록 결과 조회 (task:min:result:{minutes_task_id})
REQ-SUM-008: 최대 2개 동시 작업 제한
REQ-SUM-009: 최대 2회 재시도, default_retry_delay=30s
REQ-SUM-010: 회의록 결과 없음 → 즉시 실패 (재시도 없음)
REQ-SUM-011: OPENAI_API_KEY 빈 값 → 즉시 실패 (재시도 없음)
REQ-SUM-014: Redis 결과 캐싱 24h TTL (task:sum:result:{task_id})
"""

import json
import time
from datetime import UTC, datetime

import redis

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.pipeline.summary_generator import SummaryGenerator
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app
from backend.workers.redis_client import get_worker_redis

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
    """Redis에 요약 작업 상태 업데이트 + Pub/Sub 이벤트 발행"""
    r = _get_redis()
    status_key = f"task:sum:status:{task_id}"

    # 기존 created_at 보존
    existing_created_at = None
    existing_raw = r.get(status_key)
    if existing_raw:
        existing_data = json.loads(existing_raw)
        existing_created_at = existing_data.get("created_at")

    data: dict = {
        "task_id": task_id,
        "status": status.value,
        "progress": progress,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if existing_created_at:
        data["created_at"] = existing_created_at
    if message:
        data["message"] = message
    if error_message:
        data["error_message"] = error_message

    r.setex(status_key, settings.summary_result_ttl, json.dumps(data))

    # SSE 스트림 구독자에게 이벤트 발행
    event_type = "completed" if status == TaskStatus.completed else (
        "failed" if status == TaskStatus.failed else "status_update"
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 요약 결과 캐싱 (REQ-SUM-014: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:sum:result:{task_id}"
    r.setex(result_key, settings.summary_result_ttl, json.dumps(result))


def _extract_cached_error_message(result: dict) -> str | None:
    """레거시 error 키와 신규 error_message 키를 모두 지원"""
    return result.get("error_message") or result.get("error")


def _get_active_sum_count() -> int:
    """현재 활성 요약 작업 수 조회 (고아 항목 자동 정리)"""
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_sum_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_sum_jobs_ts")
    return pipe.execute()[1]


def _register_active_job(task_id: str) -> None:
    """활성 작업 등록"""
    r = _get_redis()
    r.zadd("active_sum_jobs_ts", {task_id: time.time()})


def _unregister_active_job(task_id: str) -> None:
    """활성 작업 해제"""
    r = _get_redis()
    r.zrem("active_sum_jobs_ts", task_id)


def summary_task(
    task_id: str,
    minutes_task_id: str,
    max_tokens: int = 4096,
    template_id: str | None = None,
) -> dict:
    """
    메인 AI 요약 생성 처리 함수 (Celery 워커에서 호출)

    Args:
        task_id: 요약 작업 UUID
        minutes_task_id: 회의록 작업 UUID (결과 조회용)
        max_tokens: OpenAI API 최대 응답 토큰 수
        template_id: 양식 ID (REQ-TMPL-004: None이면 기본 4개 항목으로 요약)

    Returns:
        완료 또는 실패 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    logger.info("요약 생성 작업 시작", task_id=task_id, minutes_task_id=minutes_task_id)

    # --- API 키 확인 (REQ-SUM-011: 빈 값이면 즉시 실패, 재시도 없음) ---
    if not settings.openai_api_key:
        error_msg = "OPENAI_API_KEY is not configured"
        logger.error("API 키 미설정으로 요약 작업 실패", task_id=task_id)
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
            "error_message": error_msg,
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
        min_status = min_result.get("status")
        if min_status and min_status != TaskStatus.completed.value:
            # BUGFIX: 회의록 실패 결과를 그대로 요약 단계에 넘기면 빈 입력으로
            # 요약이 완료 처리되거나 LLM 오류로 바뀌어 원인이 흐려집니다.
            upstream_error = _extract_cached_error_message(min_result) or (
                f"회의록 작업이 완료되지 않았습니다: status={min_status}"
            )
            raise RuntimeError(f"회의록 생성 실패로 요약을 시작할 수 없습니다: {upstream_error}")
        segments = min_result.get("segments", [])
        speaker_stats = min_result.get("speakers", [])

        _update_task_status(task_id, TaskStatus.processing, 0.3, "AI 요약 생성 중...")

        # --- 2단계: 양식 구조 로드 (REQ-TMPL-004: template_id 있으면 Redis에서 로드) ---
        template_structure: dict | None = None
        if template_id:
            tmpl_key = f"template:{template_id}"
            tmpl_raw = r.get(tmpl_key)
            if tmpl_raw:
                try:
                    tmpl_meta = json.loads(tmpl_raw)
                    template_structure = tmpl_meta.get("structure")
                    logger.info(
                        "양식 구조 로드 완료",
                        task_id=task_id,
                        template_id=template_id,
                    )
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning(
                        "양식 메타데이터 파싱 실패 - 기본 요약으로 진행",
                        task_id=task_id,
                        template_id=template_id,
                        error=str(exc),
                    )
            else:
                logger.warning(
                    "양식을 찾을 수 없음 - 기본 요약으로 진행",
                    task_id=task_id,
                    template_id=template_id,
                )

        # --- 3단계: SummaryGenerator로 요약 생성 ---
        generator = SummaryGenerator()
        summary_result = generator.generate_summary(
            segments=segments,
            speaker_stats=speaker_stats,
            api_key=settings.openai_api_key,
            model=settings.summary_model,
            max_tokens=max_tokens,
            template_structure=template_structure,
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
            # REQ-UI-001: 양식 구조 및 섹션별 내용 포함
            "sections": summary_result.sections,
            "template_structure": template_structure,
            "generation_time_seconds": generation_time,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)

        # DB 영속 저장 (best-effort, REQ-PERSIST-008)
        try:
            from backend.services.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="summary",
                status="completed",
                result_data=final_result,
            )
        except Exception:
            pass  # DB 저장 실패는 무시 (Redis에 이미 저장됨)

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
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-008)
        try:
            from backend.services.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="summary",
                status="failed",
                error_message=error_msg,
            )
        except Exception:
            pass  # DB 저장 실패는 무시

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
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-008)
        try:
            from backend.services.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="summary",
                status="failed",
                error_message=error_msg,
            )
        except Exception:
            pass  # DB 저장 실패는 무시

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
    max_tokens: int = 4096,
    template_id: str | None = None,
) -> dict:
    """
    Celery 래퍼: summary_task 호출 + 재시도 처리 (REQ-SUM-009)

    Args:
        task_id: 요약 작업 UUID
        minutes_task_id: 회의록 작업 UUID
        max_tokens: OpenAI API 최대 응답 토큰
        template_id: 양식 ID (REQ-TMPL-004: None이면 기본 요약)
    """
    try:
        return summary_task(
            task_id=task_id,
            minutes_task_id=minutes_task_id,
            max_tokens=max_tokens,
            template_id=template_id,
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
