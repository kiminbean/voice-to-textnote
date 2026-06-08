"""
Celery 전사 작업
REQ-STT-005~009: STT 처리 비동기 워커
REQ-STT-013: Redis 결과 캐싱 (24h TTL)
REQ-STT-018: 30분 초과 청크 분할 처리
"""

import json
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import redis
from celery.exceptions import SoftTimeLimitExceeded

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
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
    """Redis에 작업 상태 업데이트 + Pub/Sub 이벤트 발행 (Pipeline으로 성능 개선)"""
    r = _get_redis()
    now = datetime.now(UTC).isoformat()
    status_key = f"task:status:{task_id}"

    # 기존 created_at 보존: 먼저 읽고, 한 번만 SETEX
    existing_raw = r.get(status_key)
    existing_created_at = None
    if existing_raw:
        existing_data = json.loads(existing_raw)  # type: ignore[arg-type]
        existing_created_at = existing_data.get("created_at")

    data: dict = {
        "task_id": task_id,
        "status": status.value,
        "progress": progress,
        "updated_at": now,
    }
    if existing_created_at:
        data["created_at"] = existing_created_at
    if message:
        data["message"] = message
    if error_message:
        data["error_message"] = error_message

    r.setex(status_key, settings.cache_ttl_seconds, json.dumps(data))

    # SSE 스트림 구독자에게 이벤트 발행
    event_type = (
        "completed"
        if status == TaskStatus.completed
        else ("failed" if status == TaskStatus.failed else "status_update")
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 전사 결과 캐싱 (REQ-STT-013: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:result:{task_id}"
    r.setex(result_key, settings.cache_ttl_seconds, json.dumps(result))


def _get_active_job_count() -> int:
    """현재 활성 작업 수 조회 (만료된 항목 자동 정리)"""
    r = _get_redis()
    now = time.time()
    # 2시간 초과 항목은 작업 타임아웃(65분)을 넘었으므로 고아 항목
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_jobs_ts")
    results = pipe.execute()
    return results[1]


def _increment_active_jobs(task_id: str) -> None:
    r = _get_redis()
    now = time.time()
    pipe = r.pipeline()
    pipe.zadd("active_jobs_ts", {task_id: now})
    pipe.execute()


def _decrement_active_jobs(task_id: str) -> None:
    r = _get_redis()
    pipe = r.pipeline()
    pipe.zrem("active_jobs_ts", task_id)
    pipe.execute()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="transcription_task",
    soft_time_limit=3600,  # 60분 소프트 타임아웃 (개별 STT Celery task 기준)
    time_limit=3900,  # 65분 하드 타임아웃 (워커 강제 종료)
)
def transcription_task(
    self,
    task_id: str,
    audio_file_path: str,
    language: str = "ko",
    model_name: str = "mlx-community/whisper-small-mlx",
    original_filename: str = "",
    file_size_bytes: int = 0,
    initial_prompt: str | None = None,
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
    processing_start = datetime.now(UTC)
    temp_files: list[Path] = []  # 정리할 임시 파일 목록
    temp_dir: Path | None = None
    diarization_wav_path: Path | None = None
    task_completed = False
    retry_scheduled = False

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

        # 화자 분리(diarization)가 사용할 수 있도록 WAV를 temp_dir에 복사 보존
        wav_for_dia = settings.temp_dir / f"{task_id}_dia.wav"
        shutil.copy2(str(processed_path), str(wav_for_dia))
        diarization_wav_path = wav_for_dia

        temp_files.append(processed_path)

        duration_seconds = get_audio_duration_seconds(processed_path)
        logger.info("오디오 전처리 완료", duration_seconds=round(duration_seconds, 2))

        _update_task_status(task_id, TaskStatus.processing, 0.15, "STT 모델 준비 중...")

        # --- 2단계: STT 엔진 초기화 ---
        engine = WhisperEngine.get_instance()
        if not engine.is_loaded:
            engine.load(model_name)

        # --- 3단계: STT 추론 (청크 분할 여부 결정) ---
        # 임시 디렉토리는 미리 추적하여 split_audio가 빈 리스트를 반환해도 누수 없이 정리한다.
        chunk_output_dir = Path(tempfile.mkdtemp())
        temp_dir = chunk_output_dir
        chunks = split_audio(
            processed_path,
            chunk_duration_ms=settings.chunk_duration_ms,
            overlap_ms=settings.chunk_overlap_ms,
            output_dir=chunk_output_dir,
        )

        if chunks:
            # 30분 초과 → 청크 분할 처리 (REQ-STT-018)
            temp_dir = chunks[0].file_path.parent
            all_segments = _process_chunks(engine, chunks, task_id, language, initial_prompt)
        else:
            # 30분 이하 → 단일 파일 처리
            _update_task_status(task_id, TaskStatus.processing, 0.30, "STT 처리 중...")
            raw_result = engine.transcribe(
                str(processed_path), language=language, initial_prompt=initial_prompt
            )
            logger.info(
                "STT 원시 결과 키",
                keys=list(raw_result.keys()),
                text_preview=raw_result.get("text", "")[:200],
            )
            all_segments = _extract_segments(raw_result.get("segments", []))
            _update_task_status(task_id, TaskStatus.processing, 0.90, "결과 정리 중...")

        # --- 4단계: 결과 저장 ---
        processing_end = datetime.now(UTC)
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

        # DB 영속 저장 (best-effort, REQ-PERSIST-004)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="transcription",
                status="completed",
                result_data=final_result,
            )
        except Exception:
            pass  # DB 저장 실패는 무시 (Redis에 이미 저장됨)

        _update_task_status(task_id, TaskStatus.completed, 1.0, "전사 완료")
        task_completed = True
        logger.info(
            "전사 작업 완료",
            task_id=task_id,
            segments=len(all_segments),
            processing_time=round(processing_time, 2),
        )
        return final_result

    except SoftTimeLimitExceeded:
        # REQ-PERF-004: 시간 초과 시 실패 상태 기록 및 정리
        error_msg = "처리 시간이 60분을 초과하여 작업이 중단되었습니다"
        logger.error("전사 작업 시간 초과", task_id=task_id)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        _cache_result(
            task_id,
            {
                "task_id": task_id,
                "status": TaskStatus.failed.value,
                "error_message": error_msg,
                "created_at": processing_start.isoformat(),
            },
        )
        return {"task_id": task_id, "status": "failed", "error": error_msg}

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
        _cache_result(
            task_id,
            {
                "task_id": task_id,
                "status": TaskStatus.failed.value,
                "error_message": error_msg,
                "created_at": processing_start.isoformat(),
            },
        )

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-005)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="transcription",
                status="failed",
                error_message=error_msg,
            )
        except Exception:  # pragma: no cover
            pass  # DB 저장 실패는 무시

        # Celery 재시도 (최대 3회, 지수 백오프)
        try:
            # BUGFIX: 재시도 예약 직후 원본 업로드 파일을 finally에서 지우면
            # 다음 재시도 시 입력 파일이 사라져 즉시 FileNotFoundError가 납니다.
            # retry가 실제로 예약된 경우에만 원본 파일 정리를 미룹니다.
            retry_scheduled = True
            raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
        except self.MaxRetriesExceededError:
            retry_scheduled = False  # pragma: no cover
            logger.error("최대 재시도 초과", task_id=task_id)  # pragma: no cover
            return {"task_id": task_id, "status": "failed", "error": error_msg}  # pragma: no cover

    finally:
        _decrement_active_jobs(task_id)

        # 임시 파일 정리
        for temp_file in temp_files:
            cleanup_temp_file(temp_file)

        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # BUGFIX: STT가 실패하거나 재시도되는 경우 화자 분리용 WAV 사본은 더 이상
        # 신뢰할 수 있는 입력이 아니므로 정리합니다. 성공한 경우에만 후속 DIA에서 사용합니다.
        if not task_completed and diarization_wav_path is not None:
            cleanup_temp_file(diarization_wav_path)

        if not retry_scheduled:
            # 원본 업로드 파일 삭제 (처리 완료 또는 최종 실패 후)
            cleanup_temp_file(audio_file_path)


def _process_chunks(
    engine: WhisperEngine,
    chunks,
    task_id: str,
    language: str,
    initial_prompt: str | None = None,
) -> list[SegmentResult]:
    """청크별 순차 처리 후 결과 병합"""
    total_chunks = len(chunks)
    chunk_results = []

    for i, chunk in enumerate(chunks):
        progress = 0.20 + (i / total_chunks) * 0.65
        msg = f"STT 처리 중... (청크 {i + 1}/{total_chunks})"
        _update_task_status(task_id, TaskStatus.processing, progress, msg)

        logger.info("청크 처리", chunk_index=i, path=str(chunk.file_path))
        raw_result = engine.transcribe(
            str(chunk.file_path),
            language=language,
            initial_prompt=initial_prompt,
        )
        chunk_results.append((chunk, raw_result.get("segments", [])))

    return merge_segments(chunk_results)


def _extract_segments(raw_segments: list[dict]) -> list[SegmentResult]:
    """단일 파일 처리 결과에서 SegmentResult 목록 추출"""
    import math

    logger.info("원시 세그먼트 수", raw_count=len(raw_segments))
    for i, seg in enumerate(raw_segments):
        logger.info("원시 세그먼트", index=i, text=repr(seg.get("text", "")), keys=list(seg.keys()))

    results = []
    for i, seg in enumerate(raw_segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        avg_logprob = seg.get("avg_logprob", None)
        confidence = min(1.0, max(0.0, math.exp(avg_logprob))) if avg_logprob is not None else 0.0

        results.append(
            SegmentResult(
                id=i,
                start=round(seg.get("start", 0.0), 3),
                end=round(seg.get("end", 0.0), 3),
                text=text,
                confidence=round(confidence, 4),
            )
        )
    return results
