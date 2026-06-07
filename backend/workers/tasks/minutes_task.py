"""
Celery 회의록 생성 작업
REQ-MIN-006: POST /api/v1/minutes → Celery 비동기 처리
REQ-MIN-007: Redis에서 화자 분리 결과 조회 (task:dia:result:{diarization_task_id})
REQ-MIN-008: 최대 3개 동시 작업 제한
REQ-MIN-009: 최대 2회 재시도, default_retry_delay=30s
REQ-MIN-010: 화자 분리 결과 없음 → 즉시 실패 (재시도 없음)
REQ-MIN-013: Redis 결과 캐싱 24h TTL (task:min:result:{task_id})
"""

import json
import time
from datetime import UTC, datetime

import redis

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.pipeline.minutes_formatter import MinutesFormatter
from backend.pipeline.speaker_matcher import SpeakerMatcher, SpeakerSegment
from backend.schemas.diarization import DiarizedSegmentResult
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
    """Redis에 회의록 작업 상태 업데이트 + Pub/Sub 이벤트 발행"""
    r = _get_redis()
    status_key = f"task:min:status:{task_id}"

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

    r.setex(status_key, settings.minutes_result_ttl, json.dumps(data))

    # SSE 스트림 구독자에게 이벤트 발행
    event_type = (
        "completed"
        if status == TaskStatus.completed
        else ("failed" if status == TaskStatus.failed else "status_update")
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 회의록 결과 캐싱 (REQ-MIN-013: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:min:result:{task_id}"
    r.setex(result_key, settings.minutes_result_ttl, json.dumps(result))


def _extract_cached_error_message(result: dict) -> str | None:
    """레거시 error 키와 신규 error_message 키를 모두 지원"""
    return result.get("error_message") or result.get("error")


def _get_active_min_count() -> int:
    """현재 활성 회의록 작업 수 조회 (고아 항목 자동 정리)"""
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_min_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_min_jobs_ts")
    return pipe.execute()[1]


def _register_active_job(task_id: str) -> None:
    """활성 작업 등록"""
    r = _get_redis()
    r.zadd("active_min_jobs_ts", {task_id: time.time()})


def _unregister_active_job(task_id: str) -> None:
    """활성 작업 해제"""
    r = _get_redis()
    r.zrem("active_min_jobs_ts", task_id)


def minutes_task(
    task_id: str,
    diarization_task_id: str,
    output_format: str = "json",
    speaker_names: dict[str, str] | None = None,
    stt_task_id: str | None = None,
) -> dict:
    """
    메인 회의록 생성 처리 함수 (Celery 워커에서 호출)

    두 가지 입력 모드를 지원한다:

    1) 레거시 모드 (stt_task_id=None):
       - diarization_task가 이미 STT-DIA 매칭을 수행한 결과를 받음
       - segments에는 text가 채워져 있음

    2) 병렬 모드 (stt_task_id 제공):
       - diarization_task가 raw segments만 반환한 경우 (matched=False)
       - 이 task에서 STT 결과를 추가 조회 후 SpeakerMatcher로 매칭 수행

    Args:
        task_id: 회의록 작업 UUID
        diarization_task_id: 화자 분리 작업 UUID (결과 조회용)
        output_format: 출력 형식 ("json" 또는 "markdown")
        speaker_names: 화자 ID → 이름 매핑 (REQ-MIN-017)
        stt_task_id: STT 작업 UUID (병렬 모드에서 사후 매칭에 사용)

    Returns:
        완료 또는 실패 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    logger.info("회의록 생성 작업 시작", task_id=task_id, diarization_task_id=diarization_task_id)

    # --- 동시 작업 수 제한 확인 (REQ-MIN-008: 최대 3개) ---
    active_count = _get_active_min_count()
    if active_count >= settings.max_concurrent_minutes:
        error_msg = (
            f"동시 회의록 생성 작업 한도({settings.max_concurrent_minutes}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )
        logger.warning("회의록 작업 한도 초과", task_id=task_id, active_count=active_count)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "diarization_task_id": diarization_task_id,
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
        _update_task_status(task_id, TaskStatus.processing, 0.1, "화자 분리 결과 조회 중...")

        # --- 1단계: 화자 분리 결과 조회 (REQ-MIN-007) ---
        r = _get_redis()
        dia_result_key = f"task:dia:result:{diarization_task_id}"
        dia_result_raw = r.get(dia_result_key)

        if dia_result_raw is None:
            # 화자 분리 결과 없음 → 즉시 실패 (REQ-MIN-010: 재시도 없음)
            raise FileNotFoundError(
                f"화자 분리 결과를 찾을 수 없습니다: diarization_task_id={diarization_task_id}"
            )

        dia_result = json.loads(dia_result_raw)
        dia_status = dia_result.get("status")
        if dia_status and dia_status != TaskStatus.completed.value:
            # BUGFIX: 화자 분리 실패 결과를 빈 segments로 처리하면 회의록이
            # 잘못 completed 될 수 있습니다. 선행 DIA 실패를 그대로 전파합니다.
            upstream_error = _extract_cached_error_message(dia_result) or (
                f"화자 분리 작업이 완료되지 않았습니다: status={dia_status}"
            )
            raise RuntimeError(f"화자 분리 실패로 회의록을 생성할 수 없습니다: {upstream_error}")
        raw_segments = dia_result.get("segments", [])
        dia_matched = dia_result.get("matched", True)  # 기존 결과는 매칭됐다고 가정

        _update_task_status(task_id, TaskStatus.processing, 0.3, "회의록 포맷 변환 중...")

        # --- 2단계: 매칭 수행 (병렬 모드에서 dia가 raw segments만 반환한 경우) ---
        if not dia_matched:
            # 병렬 모드: STT 결과를 조회해 SpeakerMatcher 사용
            if not stt_task_id:
                raise RuntimeError(
                    "매칭되지 않은 dia 결과(matched=False)를 받았지만 "
                    "stt_task_id가 제공되지 않았습니다. 클라이언트가 두 ID를 모두 전달해야 합니다."
                )

            stt_result_key = f"task:result:{stt_task_id}"
            stt_result_raw = r.get(stt_result_key)
            if stt_result_raw is None:
                raise FileNotFoundError(f"STT 결과를 찾을 수 없습니다: stt_task_id={stt_task_id}")
            stt_result = json.loads(stt_result_raw)  # pragma: no cover
            if stt_result.get("status") != TaskStatus.completed.value:
                upstream_error = _extract_cached_error_message(stt_result) or (  # pragma: no cover
                    f"STT 작업이 완료되지 않았습니다: status={stt_result.get('status')}"
                )
                raise RuntimeError(  # pragma: no cover
                    f"STT 작업 실패로 회의록을 생성할 수 없습니다: {upstream_error}"
                )

            stt_segments = stt_result.get("segments", [])
            dia_speaker_segments = [
                SpeakerSegment(
                    speaker_id=seg["speaker_id"],
                    start=seg["start"],
                    end=seg["end"],
                )
                for seg in raw_segments
            ]

            matcher = SpeakerMatcher()
            matched = matcher.match(stt_segments, dia_speaker_segments)
            diarized_segments = matched
        else:
            # 레거시 모드: 이미 매칭된 segments를 변환
            diarized_segments = [DiarizedSegmentResult(**seg) for seg in raw_segments]

        # 전체 대화 시간 계산
        total_duration = max((seg.end for seg in diarized_segments), default=0.0)

        # --- 3단계: MinutesFormatter로 회의록 생성 ---
        formatter = MinutesFormatter(speaker_names=speaker_names)
        minutes_segments = formatter.format_minutes(diarized_segments)

        _update_task_status(task_id, TaskStatus.processing, 0.6, "화자 통계 계산 중...")

        # --- 4단계: 화자 통계 계산 (REQ-MIN-002) ---
        speaker_stats = formatter.calculate_speaker_stats(minutes_segments, total_duration)

        # --- 5단계: 마크다운 생성 (REQ-MIN-003, 조건부) ---
        markdown_content = None
        if output_format == "markdown":
            markdown_content = formatter.to_markdown(minutes_segments)

        _update_task_status(task_id, TaskStatus.processing, 0.9, "결과 저장 중...")

        processing_end = datetime.now(UTC)

        # --- 6단계: 결과 저장 (REQ-MIN-004: JSON 구조화) ---
        final_result = {
            "task_id": task_id,
            "diarization_task_id": diarization_task_id,
            "status": TaskStatus.completed.value,
            "segments": [seg.model_dump() for seg in minutes_segments],
            "speakers": [s.model_dump() for s in speaker_stats],
            "total_duration": total_duration,
            "total_speakers": len(speaker_stats),
            "markdown": markdown_content,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)

        # DB 영속 저장 (best-effort, REQ-PERSIST-006)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="minutes",
                status="completed",
                result_data=final_result,
            )
        except Exception:
            pass  # DB 저장 실패는 무시 (Redis에 이미 저장됨)

        _update_task_status(task_id, TaskStatus.completed, 1.0, "회의록 생성 완료")

        logger.info(
            "회의록 생성 완료",
            task_id=task_id,
            segments=len(minutes_segments),
            speakers=len(speaker_stats),
        )
        return final_result

    except FileNotFoundError as exc:
        # 화자 분리 결과 없음 → 즉시 실패 (REQ-MIN-010: 재시도 없음)
        error_msg = str(exc)
        logger.error("회의록 생성 실패 (화자 분리 결과 없음)", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "diarization_task_id": diarization_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="minutes",
                status="failed",
                error_message=error_msg,
            )
        except Exception:  # pragma: no cover
            pass  # DB 저장 실패는 무시

        return failed_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("회의록 생성 실패", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "diarization_task_id": diarization_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="minutes",
                status="failed",
                error_message=error_msg,
            )
        except Exception:  # pragma: no cover
            pass  # DB 저장 실패는 무시

        return failed_result

    finally:
        _unregister_active_job(task_id)


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="minutes_task",
)
def minutes_celery_task(
    self,
    task_id: str,
    diarization_task_id: str,
    output_format: str = "json",
    speaker_names: dict[str, str] | None = None,
    stt_task_id: str | None = None,
) -> dict:
    """
    Celery 래퍼: minutes_task 호출 + 재시도 처리 (REQ-MIN-009)

    Args:
        task_id: 회의록 작업 UUID
        diarization_task_id: 화자 분리 작업 UUID
        output_format: 출력 형식 ("json" 또는 "markdown")
        speaker_names: 화자 이름 매핑
        stt_task_id: STT 작업 UUID (병렬 모드 - dia가 matched=False일 때 매칭에 사용)
    """
    try:
        return minutes_task(
            task_id=task_id,
            diarization_task_id=diarization_task_id,
            output_format=output_format,
            speaker_names=speaker_names,
            stt_task_id=stt_task_id,
        )
    except FileNotFoundError as exc:
        # 화자 분리 결과 없음 → 재시도 안 함 (REQ-MIN-010)
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        # 일반 오류 → 재시도 (최대 2회, delay=30s) (REQ-MIN-009)
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}
