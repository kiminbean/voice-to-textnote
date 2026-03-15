"""
Celery 전사 작업
REQ-STT-005~009: STT 처리 비동기 워커
REQ-STT-013: Redis 결과 캐싱 (24h TTL)
REQ-STT-018: 30분 초과 청크 분할 처리
"""
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import redis

from backend.app.config import settings
from backend.ml.stt_engine import WhisperEngine
from backend.pipeline.audio_processor import (
    cleanup_temp_file,
    convert_and_normalize,
    get_audio_duration_seconds,
)
from backend.pipeline.chunk_manager import merge_segments, split_audio
from backend.schemas.transcription import SegmentResult, TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app

logger = get_logger(__name__)

# Redis 동기 클라이언트 (Celery 워커는 동기 환경)
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
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
    """Redis에 작업 상태 업데이트"""
    r = _get_redis()
    data = {
        "task_id": task_id,
        "status": status.value,
        "progress": progress,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if message:
        data["message"] = message
    if error_message:
        data["error_message"] = error_message

    status_key = f"task:status:{task_id}"
    r.setex(status_key, settings.cache_ttl_seconds, json.dumps(data))


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 전사 결과 캐싱 (REQ-STT-013: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:result:{task_id}"
    r.setex(result_key, settings.cache_ttl_seconds, json.dumps(result))


def _get_active_job_count() -> int:
    """현재 활성 작업 수 조회 (동시 처리 제한용)"""
    r = _get_redis()
    count_str = r.get("active_job_count")
    return int(count_str) if count_str else 0


def _increment_active_jobs(task_id: str) -> None:
    r = _get_redis()
    pipe = r.pipeline()
    pipe.incr("active_job_count")
    pipe.sadd("active_jobs", task_id)
    pipe.execute()


def _decrement_active_jobs(task_id: str) -> None:
    r = _get_redis()
    pipe = r.pipeline()
    pipe.decr("active_job_count")
    pipe.srem("active_jobs", task_id)
    pipe.execute()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="transcription_task",
)
def transcription_task(
    self,
    task_id: str,
    audio_file_path: str,
    language: str = "ko",
    model_name: str = "mlx-community/whisper-large-v3-turbo",
    original_filename: str = "",
    file_size_bytes: int = 0,
) -> dict:
    """
    메인 STT 처리 Celery 작업

    Args:
        task_id: 전사 작업 UUID
        audio_file_path: 업로드된 원본 오디오 파일 경로
        language: 전사 언어 코드 (기본: "ko")
        model_name: Whisper 모델 ID
        original_filename: 원본 파일명
        file_size_bytes: 파일 크기 (bytes)
    """
    processing_start = datetime.now(timezone.utc)
    temp_files: list[Path] = []  # 정리할 임시 파일 목록
    temp_dir: Path | None = None

    logger.info("전사 작업 시작", task_id=task_id, language=language)

    # 동시 처리 수 체크 및 등록
    _increment_active_jobs(task_id)

    try:
        _update_task_status(task_id, TaskStatus.processing, 0.05, "오디오 전처리 중...")

        # --- 1단계: 오디오 전처리 ---
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일 없음: {audio_file_path}")

        # 16kHz 모노 WAV 변환 + 정규화 (REQ-STT-015, REQ-STT-016)
        processed_path = convert_and_normalize(audio_path)
        temp_files.append(processed_path)

        duration_seconds = get_audio_duration_seconds(processed_path)
        logger.info("오디오 전처리 완료", duration_seconds=round(duration_seconds, 2))

        _update_task_status(task_id, TaskStatus.processing, 0.15, "STT 모델 준비 중...")

        # --- 2단계: STT 엔진 초기화 ---
        engine = WhisperEngine.get_instance()
        if not engine.is_loaded:
            engine.load(model_name)

        # --- 3단계: STT 추론 (청크 분할 여부 결정) ---
        chunks = split_audio(
            processed_path,
            chunk_duration_ms=settings.chunk_duration_ms,
            overlap_ms=settings.chunk_overlap_ms,
            output_dir=tempfile.mkdtemp(),
        )

        if chunks:
            # 30분 초과 → 청크 분할 처리 (REQ-STT-018)
            temp_dir = chunks[0].file_path.parent
            all_segments = _process_chunks(engine, chunks, task_id, language)
        else:
            # 30분 이하 → 단일 파일 처리
            _update_task_status(task_id, TaskStatus.processing, 0.30, "STT 처리 중...")
            raw_result = engine.transcribe(str(processed_path), language=language)
            all_segments = _extract_segments(raw_result.get("segments", []))
            _update_task_status(task_id, TaskStatus.processing, 0.90, "결과 정리 중...")

        # --- 4단계: 결과 저장 ---
        processing_end = datetime.now(timezone.utc)
        processing_time = (processing_end - processing_start).total_seconds()

        final_result = {
            "task_id": task_id,
            "status": TaskStatus.completed.value,
            "language": language,
            "duration": round(duration_seconds, 3),
            "model": model_name,
            "segments": [seg.model_dump() for seg in all_segments],
            "metadata": {
                "file_name": original_filename,
                "file_size_bytes": file_size_bytes,
                "sample_rate": 16000,
                "processing_time_seconds": round(processing_time, 2),
            },
            "created_at": processing_start.isoformat(),
            "completed_at": processing_end.isoformat(),
        }

        # Redis 캐싱 (REQ-STT-013: 24h TTL)
        _cache_result(task_id, final_result)

        # 결과 파일 시스템 영구 저장 (캐시 미스 대비)
        result_file = settings.results_dir / f"{task_id}.json"
        result_file.write_text(json.dumps(final_result, ensure_ascii=False), encoding="utf-8")

        _update_task_status(task_id, TaskStatus.completed, 1.0, "전사 완료")
        logger.info(
            "전사 작업 완료",
            task_id=task_id,
            segments=len(all_segments),
            processing_time=round(processing_time, 2),
        )
        return final_result

    except Exception as exc:
        # REQ-STT-009: 부분 결과 저장 금지, failed 상태 기록
        error_msg = str(exc)
        logger.error("전사 작업 실패", task_id=task_id, error=error_msg)

        _update_task_status(
            task_id,
            TaskStatus.failed,
            0.0,
            error_message=error_msg,
        )

        # Redis에 실패 상태 저장
        _cache_result(task_id, {
            "task_id": task_id,
            "status": TaskStatus.failed.value,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        })

        # Celery 재시도 (최대 3회, 지수 백오프)
        try:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
        except self.MaxRetriesExceededError:
            logger.error("최대 재시도 초과", task_id=task_id)
            return {"task_id": task_id, "status": "failed", "error": error_msg}

    finally:
        _decrement_active_jobs(task_id)

        # 임시 파일 정리
        for temp_file in temp_files:
            cleanup_temp_file(temp_file)

        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # 원본 업로드 파일 삭제 (처리 완료 후)
        cleanup_temp_file(audio_file_path)


def _process_chunks(
    engine: WhisperEngine,
    chunks,
    task_id: str,
    language: str,
) -> list[SegmentResult]:
    """청크별 순차 처리 후 결과 병합"""
    total_chunks = len(chunks)
    chunk_results = []

    for i, chunk in enumerate(chunks):
        progress = 0.20 + (i / total_chunks) * 0.65
        msg = f"STT 처리 중... (청크 {i + 1}/{total_chunks})"
        _update_task_status(task_id, TaskStatus.processing, progress, msg)

        logger.info("청크 처리", chunk_index=i, path=str(chunk.file_path))
        raw_result = engine.transcribe(str(chunk.file_path), language=language)
        chunk_results.append((chunk, raw_result.get("segments", [])))

    return merge_segments(chunk_results)


def _extract_segments(raw_segments: list[dict]) -> list[SegmentResult]:
    """단일 파일 처리 결과에서 SegmentResult 목록 추출"""
    import math

    results = []
    for i, seg in enumerate(raw_segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        avg_logprob = seg.get("avg_logprob", None)
        confidence = (
            min(1.0, max(0.0, math.exp(avg_logprob)))
            if avg_logprob is not None
            else 0.0
        )

        results.append(SegmentResult(
            id=i,
            start=round(seg.get("start", 0.0), 3),
            end=round(seg.get("end", 0.0), 3),
            text=text,
            confidence=round(confidence, 4),
        ))
    return results
