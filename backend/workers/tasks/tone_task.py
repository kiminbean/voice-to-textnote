"""
SPEC-TONE-001: Celery 발화 톤/운율 분석 작업
REQ-TONE-004: DIA wav 없으면 skipped 반환
REQ-TONE-005: tone_task 완료/실패 후 DIA wav 삭제 (orphan 방지)
REQ-TONE-006: tone_task 실패 시 다른 파이프라인 태스크 무영향
REQ-TONE-008: celery_app include 리스트 등록
"""

import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import redis
from celery.exceptions import SoftTimeLimitExceeded

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.ml.tone_engine import ToneEngine
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app
from backend.workers.redis_client import get_worker_redis

logger = get_logger(__name__)


def _get_redis() -> redis.Redis:
    return get_worker_redis()


def _update_task_status(
    task_id: str,
    status: TaskStatus,
    progress: float = 0.0,
    message: str | None = None,
    error_message: str | None = None,
) -> None:
    r = _get_redis()
    status_key = f"task:tone:status:{task_id}"

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

    r.setex(status_key, settings.tone_result_ttl, json.dumps(data))

    event_type = (
        "completed"
        if status == TaskStatus.completed
        else ("failed" if status == TaskStatus.failed else "status_update")
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_result(task_id: str, result: dict) -> None:
    r = _get_redis()
    result_key = f"task:tone:result:{task_id}"
    r.setex(result_key, settings.tone_result_ttl, json.dumps(result))


def _get_active_tone_count() -> int:
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_tone_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_tone_jobs_ts")
    return pipe.execute()[1]


def _register_active_job(task_id: str) -> None:
    r = _get_redis()
    r.zadd("active_tone_jobs_ts", {task_id: time.time()})


def _unregister_active_job(task_id: str) -> None:
    r = _get_redis()
    r.zrem("active_tone_jobs_ts", task_id)


def _build_speaker_summary(
    segments: list[dict],
) -> list[dict]:
    """화자별 톤 분포 요약 집계"""
    speaker_data: dict[str, dict] = {}
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        tone = seg.get("tone", "unknown")
        prosody = seg.get("prosody_features", {})

        if speaker not in speaker_data:
            speaker_data[speaker] = {
                "speaker": speaker,
                "tones": [],
                "f0_values": [],
                "rms_values": [],
            }

        speaker_data[speaker]["tones"].append(tone)
        if prosody.get("f0_mean", 0) > 0:
            speaker_data[speaker]["f0_values"].append(prosody["f0_mean"])
        if prosody.get("rms_energy", 0) > 0:
            speaker_data[speaker]["rms_values"].append(prosody["rms_energy"])

    result = []
    for speaker, data in speaker_data.items():
        tone_dist = Counter(data["tones"])
        dominant_tone = tone_dist.most_common(1)[0][0] if data["tones"] else "unknown"
        avg_f0 = sum(data["f0_values"]) / len(data["f0_values"]) if data["f0_values"] else 0.0
        avg_rms = sum(data["rms_values"]) / len(data["rms_values"]) if data["rms_values"] else 0.0

        result.append(
            {
                "speaker": speaker,
                "dominant_tone": dominant_tone,
                "tone_distribution": dict(tone_dist),
                "avg_pitch": round(avg_f0, 2),
                "avg_energy": round(avg_rms, 6),
            }
        )

    return result


def _compute_overall_tone(segments: list[dict]) -> str:
    """전체 세그먼트에서 가장 빈도 높은 톤 반환"""
    valid_tones = [s.get("tone", "unknown") for s in segments if s.get("tone") not in ("skipped", None)]
    if not valid_tones:
        return "unknown"
    return Counter(valid_tones).most_common(1)[0][0]


def tone_task(
    task_id: str,
    dia_task_id: str,
    dia_wav_path: str,
    segments: list[dict],
) -> dict:
    """
    톤/운율 분석 메인 처리 함수

    Args:
        task_id: tone 작업 UUID
        dia_task_id: 상위 DIA 작업 UUID (참조용)
        dia_wav_path: DIA wav 파일 경로 (tone_task 완료 후 삭제됨, REQ-TONE-005)
        segments: SpeakerSegment 리스트 [{start, end, speaker}, ...]

    Returns:
        완료/실패/skipped 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    logger.info(
        "톤 분석 작업 시작",
        task_id=task_id,
        dia_task_id=dia_task_id,
        wav_path=dia_wav_path,
    )

    # REQ-TONE-004: DIA wav 없으면 skipped 상태로 종료
    wav_path = Path(dia_wav_path)
    if not wav_path.exists():
        logger.warning("DIA wav 파일 없음, 톤 분석 스킵", task_id=task_id, path=dia_wav_path)
        _update_task_status(task_id, TaskStatus.completed, 1.0, "DIA wav 없음 — 스킵")
        skipped_result = {
            "task_id": task_id,
            "dia_task_id": dia_task_id,
            "status": "skipped",
            "segments": [],
            "speakers": [],
            "overall_tone": "unknown",
            "error_message": f"DIA wav 파일을 찾을 수 없습니다: {dia_wav_path}",
            "created_at": processing_start.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        }
        _cache_result(task_id, skipped_result)
        return skipped_result

    # 동시 작업 수 제한 (메모리 보호)
    active_count = _get_active_tone_count()
    if active_count >= settings.max_concurrent_tone:
        error_msg = f"동시 톤 분석 작업 한도({settings.max_concurrent_tone}개)를 초과했습니다."
        logger.warning("톤 분석 한도 초과", task_id=task_id, active_count=active_count)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "dia_task_id": dia_task_id,
            "status": "rejected",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    _register_active_job(task_id)

    try:
        _update_task_status(task_id, TaskStatus.processing, 0.1, "톤 분석 준비 중...")

        engine = ToneEngine.get_instance()
        _update_task_status(task_id, TaskStatus.processing, 0.3, "세그먼트별 톤 분석 중...")

        tone_segments = engine.analyze_segments(dia_wav_path, segments)

        _update_task_status(task_id, TaskStatus.processing, 0.9, "결과 저장 중...")

        processing_end = datetime.now(UTC)
        generation_time = (processing_end - processing_start).total_seconds()

        speaker_summary = _build_speaker_summary(tone_segments)
        overall_tone = _compute_overall_tone(tone_segments)

        final_result = {
            "task_id": task_id,
            "dia_task_id": dia_task_id,
            "status": TaskStatus.completed.value,
            "segments": tone_segments,
            "speakers": speaker_summary,
            "overall_tone": overall_tone,
            "generation_time_seconds": generation_time,
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)
        _update_task_status(task_id, TaskStatus.completed, 1.0, "톤 분석 완료")

        logger.info(
            "톤 분석 완료",
            task_id=task_id,
            segments=len(tone_segments),
            overall_tone=overall_tone,
            generation_time=generation_time,
        )
        return final_result

    except SoftTimeLimitExceeded:
        error_msg = "톤 분석 시간 초과"
        logger.error("톤 분석 시간 초과", task_id=task_id)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "dia_task_id": dia_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("톤 분석 실패", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "dia_task_id": dia_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    finally:
        # REQ-TONE-005: tone_task 완료/실패와 무관하게 DIA wav 삭제 (orphan 방지)
        _unregister_active_job(task_id)
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="tone_task",
    soft_time_limit=300,
    time_limit=360,
)
def tone_celery_task(
    self,
    task_id: str,
    dia_task_id: str,
    dia_wav_path: str,
    segments: list[dict],
) -> dict:
    """Celery 래퍼: 톤 분석 + 재시도 처리"""
    try:
        return tone_task(
            task_id=task_id,
            dia_task_id=dia_task_id,
            dia_wav_path=dia_wav_path,
            segments=segments,
        )
    except SoftTimeLimitExceeded:
        return {"task_id": task_id, "status": "failed", "error": "시간 초과"}
    except Exception as exc:
        try:
            raise self.retry(exc=exc, countdown=30)
        except self.MaxRetriesExceededError:
            logger.error("톤 분석 최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}
