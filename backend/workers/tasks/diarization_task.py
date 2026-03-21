"""
Celery 화자 분리 작업
REQ-DIA-013: Celery 비동기 화자 분리 처리
REQ-DIA-014: 최대 2개 동시 작업 제한
REQ-DIA-015: Redis 결과 캐싱 (24h TTL)
REQ-DIA-016: WAV 파일/STT 결과 없음 → 즉시 실패
REQ-DIA-017: 오류 시 failed 상태 저장
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import redis

from backend.app.config import settings
from backend.ml.diarization_engine import DiarizationEngine
from backend.pipeline.speaker_matcher import SpeakerMatcher
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
    """Redis에 화자 분리 작업 상태 업데이트"""
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

    status_key = f"task:dia:status:{task_id}"
    r.setex(status_key, settings.diarization_result_ttl, json.dumps(data))


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 화자 분리 결과 캐싱 (REQ-DIA-015: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:dia:result:{task_id}"
    r.setex(result_key, settings.diarization_result_ttl, json.dumps(result))


def _get_active_dia_count() -> int:
    """현재 활성 화자 분리 작업 수 조회"""
    r = _get_redis()
    return r.scard("active_dia_jobs") or 0


def _register_active_job(task_id: str) -> None:
    """활성 작업 등록"""
    r = _get_redis()
    r.sadd("active_dia_jobs", task_id)


def _unregister_active_job(task_id: str) -> None:
    """활성 작업 해제"""
    r = _get_redis()
    r.srem("active_dia_jobs", task_id)


def diarization_task(
    task_id: str,
    stt_task_id: str,
    num_speakers: int | None = None,
    min_speakers: int = 1,
    max_speakers: int = 10,
) -> dict:
    """
    메인 화자 분리 처리 함수 (Celery 워커에서 호출)

    Args:
        task_id: 화자 분리 작업 UUID
        stt_task_id: STT 작업 UUID (결과 조회용)
        num_speakers: 예상 화자 수 (None이면 자동 감지)
        min_speakers: 최소 화자 수
        max_speakers: 최대 화자 수

    Returns:
        완료 또는 실패 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    logger.info("화자 분리 작업 시작", task_id=task_id, stt_task_id=stt_task_id)

    # --- 동시 작업 수 제한 확인 (REQ-DIA-014: 최대 2개) ---
    active_count = _get_active_dia_count()
    if active_count >= settings.max_concurrent_diarizations:
        error_msg = (
            f"동시 화자 분리 작업 한도({settings.max_concurrent_diarizations}개)를 "
            "초과했습니다. 잠시 후 재시도하세요."
        )
        logger.warning("화자 분리 작업 한도 초과", task_id=task_id, active_count=active_count)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "stt_task_id": stt_task_id,
            "status": "rejected",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    # 활성 작업 등록
    _register_active_job(task_id)

    try:
        _update_task_status(task_id, TaskStatus.processing, 0.05, "STT 결과 조회 중...")

        # --- 1단계: STT 결과 조회 ---
        r = _get_redis()
        stt_result_key = f"task:result:{stt_task_id}"
        stt_result_raw = r.get(stt_result_key)

        if stt_result_raw is None:
            raise FileNotFoundError(f"STT 결과를 찾을 수 없습니다: stt_task_id={stt_task_id}")

        stt_result = json.loads(stt_result_raw)
        stt_segments = stt_result.get("segments", [])

        _update_task_status(task_id, TaskStatus.processing, 0.10, "WAV 파일 확인 중...")

        # --- 2단계: WAV 파일 확인 ---
        wav_path = Path(settings.temp_dir) / f"{stt_task_id}.wav"
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV 파일을 찾을 수 없습니다: {wav_path}")

        _update_task_status(task_id, TaskStatus.processing, 0.20, "화자 분리 모델 준비 중...")

        # --- 3단계: DiarizationEngine 초기화 ---
        engine = DiarizationEngine.get_instance()
        if not engine.is_loaded:
            engine.load(
                hf_token=settings.huggingface_token,
                model_name=settings.diarization_model,
            )

        _update_task_status(task_id, TaskStatus.processing, 0.30, "화자 분리 처리 중...")

        # --- 4단계: 화자 분리 실행 ---
        dia_segments = engine.diarize(wav_path)

        _update_task_status(task_id, TaskStatus.processing, 0.80, "STT 결과와 화자 매칭 중...")

        # --- 5단계: STT 세그먼트와 화자 매핑 ---
        matcher = SpeakerMatcher()
        diarized_segments = matcher.match(stt_segments, dia_segments)

        # 화자 통계 생성
        speaker_stats: dict[str, dict] = {}
        for seg in diarized_segments:
            if seg.speaker_id is not None:
                if seg.speaker_id not in speaker_stats:
                    speaker_stats[seg.speaker_id] = {
                        "speaker_id": seg.speaker_id,
                        "total_speaking_time": 0.0,
                        "segment_count": 0,
                    }
                speaker_stats[seg.speaker_id]["total_speaking_time"] += seg.end - seg.start
                speaker_stats[seg.speaker_id]["segment_count"] += 1

        processing_end = datetime.now(UTC)

        # --- 6단계: 결과 저장 ---
        final_result = {
            "task_id": task_id,
            "stt_task_id": stt_task_id,
            "status": TaskStatus.completed.value,
            "segments": [seg.model_dump() for seg in diarized_segments],
            "speakers": list(speaker_stats.values()),
            "num_speakers": len(speaker_stats),
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        _cache_result(task_id, final_result)

        # DB 영속 저장 (best-effort, REQ-PERSIST-006)
        try:
            from backend.db.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="diarization",
                status="completed",
                result_data=final_result,
            )
        except Exception:
            pass  # DB 저장 실패는 무시 (Redis에 이미 저장됨)

        _update_task_status(task_id, TaskStatus.completed, 1.0, "화자 분리 완료")

        logger.info(
            "화자 분리 작업 완료",
            task_id=task_id,
            segments=len(diarized_segments),
            speakers=len(speaker_stats),
        )
        return final_result

    except FileNotFoundError as exc:
        # WAV 파일 또는 STT 결과 없음 → 즉시 실패 (재시도 없음)
        error_msg = str(exc)
        logger.error("화자 분리 작업 실패 (파일 없음)", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "stt_task_id": stt_task_id,
            "status": "failed",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.db.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="diarization",
                status="failed",
                error_message=error_msg,
            )
        except Exception:
            pass  # DB 저장 실패는 무시

        return failed_result

    except Exception as exc:
        error_msg = str(exc)
        logger.error("화자 분리 작업 실패", task_id=task_id, error=error_msg)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "stt_task_id": stt_task_id,
            "status": "failed",
            "error": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.db.sync_service import persist_task_result
            persist_task_result(
                task_id=task_id,
                task_type="diarization",
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
    max_retries=3,
    default_retry_delay=60,
    name="diarization_task",
)
def diarization_celery_task(
    self,
    task_id: str,
    stt_task_id: str,
    num_speakers: int | None = None,
    min_speakers: int = 1,
    max_speakers: int = 10,
) -> dict:
    """
    Celery 래퍼: diarization_task 호출 + 재시도 처리

    Args:
        task_id: 화자 분리 작업 UUID
        stt_task_id: STT 작업 UUID
        num_speakers: 예상 화자 수
        min_speakers: 최소 화자 수
        max_speakers: 최대 화자 수
    """
    try:
        return diarization_task(
            task_id=task_id,
            stt_task_id=stt_task_id,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
    except FileNotFoundError as exc:
        # 파일 없음 → 재시도 안 함
        return {"task_id": task_id, "status": "failed", "error": str(exc)}
    except Exception as exc:
        # 일반 오류 → 지수 백오프로 재시도 (최대 3회)
        try:
            raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
        except self.MaxRetriesExceededError:
            logger.error("최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": str(exc)}
