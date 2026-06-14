"""
Celery 화자 분리 작업
REQ-DIA-013: Celery 비동기 화자 분리 처리
REQ-DIA-014: 최대 2개 동시 작업 제한
REQ-DIA-015: Redis 결과 캐싱 (24h TTL)
REQ-DIA-016: WAV 파일/STT 결과 없음 → 즉시 실패
REQ-DIA-017: 오류 시 failed 상태 저장
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import redis
from celery.exceptions import SoftTimeLimitExceeded

from backend.app.config import settings
from backend.events.publisher import publish_task_event_sync
from backend.ml.diarization_engine import DiarizationEngine
from backend.pipeline.speaker_matcher import SpeakerMatcher
from backend.schemas.transcription import TaskStatus
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app
from backend.workers.redis_client import get_worker_redis

logger = get_logger(__name__)


def _trigger_tone_task(dia_task_id: str, dia_wav_path: str, segments: list[dict]) -> None:
    """SPEC-TONE-001: DIA 완료 후 tone_task 트리거 (REQ-TONE-007)

    REQ-TONE-011: tone_model이 빈 문자열이면 트리거하지 않는다.
    task_id에 dia_task_id를 사용 — 클라이언트가 DIA task_id로 tone 결과를 조회할 수 있도록.
    """
    if not settings.tone_model:
        return

    try:
        from backend.workers.tasks.tone_task import tone_celery_task

        tone_celery_task.delay(
            task_id=dia_task_id,
            dia_task_id=dia_task_id,
            dia_wav_path=dia_wav_path,
            segments=segments,
        )
        logger.info(
            "톤 분석 태스크 트리거",
            dia_task_id=dia_task_id,
            wav_path=dia_wav_path,
        )
    except Exception as e:
        logger.error("톤 분석 태스크 트리거 실패 (파이프라인 계속)", error=str(e))


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
    """Redis에 화자 분리 작업 상태 업데이트 + Pub/Sub 이벤트 발행"""
    r = _get_redis()
    status_key = f"task:dia:status:{task_id}"

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

    r.setex(status_key, settings.diarization_result_ttl, json.dumps(data))

    # SSE 스트림 구독자에게 이벤트 발행
    event_type = (
        "completed"
        if status == TaskStatus.completed
        else ("failed" if status == TaskStatus.failed else "status_update")
    )
    publish_task_event_sync(r, task_id, event_type, data)


def _cache_result(task_id: str, result: dict) -> None:
    """Redis에 화자 분리 결과 캐싱 (REQ-DIA-015: 24h TTL)"""
    r = _get_redis()
    result_key = f"task:dia:result:{task_id}"
    r.setex(result_key, settings.diarization_result_ttl, json.dumps(result))


def _extract_cached_error_message(result: dict) -> str | None:
    """레거시 error 키와 신규 error_message 키를 모두 지원"""
    return result.get("error_message") or result.get("error")


def _get_active_dia_count() -> int:
    """현재 활성 화자 분리 작업 수 조회 (고아 항목 자동 정리)"""
    r = _get_redis()
    now = time.time()
    stale_cutoff = now - 7200
    pipe = r.pipeline()
    pipe.zremrangebyscore("active_dia_jobs_ts", "-inf", stale_cutoff)
    pipe.zcard("active_dia_jobs_ts")
    return pipe.execute()[1]


def _register_active_job(task_id: str) -> None:
    """활성 작업 등록"""
    r = _get_redis()
    r.zadd("active_dia_jobs_ts", {task_id: time.time()})


def _unregister_active_job(task_id: str) -> None:
    """활성 작업 해제"""
    r = _get_redis()
    r.zrem("active_dia_jobs_ts", task_id)


def diarization_task(
    task_id: str,
    stt_task_id: str | None = None,
    num_speakers: int | None = None,
    min_speakers: int = 1,
    max_speakers: int = 10,
    audio_path: str | None = None,
) -> dict:
    """
    메인 화자 분리 처리 함수 (Celery 워커에서 호출)

    두 가지 운영 모드를 지원한다:

    1) 레거시 직렬 모드 (audio_path is None, stt_task_id 필수):
       - STT 완료 결과를 Redis에서 조회 (기다리지 않음, 없으면 실패)
       - 화자 분리 후 STT segments와 매칭한 결과를 반환

    2) 병렬 모드 (audio_path 제공, stt_task_id 선택):
       - WAV 파일을 직접 받아 STT 완료를 기다리지 않고 즉시 화자 분리
       - stt_task_id를 함께 받으면 결과 도착 시점에 매칭, 없으면 매칭 skip
         (매칭되지 않은 raw segments는 minutes_task에서 STT와 결합)

    Args:
        task_id: 화자 분리 작업 UUID
        stt_task_id: STT 작업 UUID (병렬 모드에서는 선택, 매칭에만 사용)
        num_speakers: 예상 화자 수 (None이면 자동 감지)
        min_speakers: 최소 화자 수
        max_speakers: 최대 화자 수
        audio_path: WAV 파일 직접 경로 (병렬 모드)

    Returns:
        완료 또는 실패 결과 딕셔너리
    """
    processing_start = datetime.now(UTC)
    parallel_mode = audio_path is not None
    logger.info(
        "화자 분리 작업 시작",
        task_id=task_id,
        stt_task_id=stt_task_id,
        parallel_mode=parallel_mode,
    )

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
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

    # 활성 작업 등록
    _register_active_job(task_id)

    try:
        r = _get_redis()
        stt_segments: list[dict] = []

        if parallel_mode:
            # --- 병렬 모드: STT 결과를 기다리지 않고 WAV 직접 처리 ---
            _update_task_status(task_id, TaskStatus.processing, 0.05, "WAV 파일 확인 중...")
            wav_path = Path(audio_path)  # type: ignore[arg-type]
            if not wav_path.exists():
                raise FileNotFoundError(f"WAV 파일을 찾을 수 없습니다: {wav_path}")
        else:
            # --- 레거시 직렬 모드: STT 결과 조회 후 매칭 ---
            if not stt_task_id:
                raise RuntimeError("레거시 모드에서는 stt_task_id가 필요합니다.")

            _update_task_status(task_id, TaskStatus.processing, 0.05, "STT 결과 조회 중...")
            stt_result_key = f"task:result:{stt_task_id}"
            stt_result_raw = r.get(stt_result_key)

            if stt_result_raw is None:
                raise FileNotFoundError(f"STT 결과를 찾을 수 없습니다: stt_task_id={stt_task_id}")

            stt_result = json.loads(stt_result_raw)
            stt_status = stt_result.get("status")
            if stt_status and stt_status != TaskStatus.completed.value:
                upstream_error = _extract_cached_error_message(stt_result) or (
                    f"STT 작업이 완료되지 않았습니다: status={stt_status}"
                )
                raise RuntimeError(
                    f"STT 작업 실패로 화자 분리를 시작할 수 없습니다: {upstream_error}"
                )
            stt_segments = stt_result.get("segments", [])

            _update_task_status(task_id, TaskStatus.processing, 0.10, "WAV 파일 확인 중...")

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

        # --- 4단계: 화자 분리 실행 (REQ-PERF-001: 긴 오디오 청크 분할) ---
        from backend.pipeline.audio_processor import get_audio_duration_seconds

        audio_duration = get_audio_duration_seconds(wav_path)
        threshold_sec = settings.dia_chunk_threshold_minutes * 60

        if audio_duration >= threshold_sec:
            # BUGFIX: 설정 설명은 "15분 이상"인데 구현은 "15분 초과"라서
            # 정확히 15분인 파일만 단일 처리로 빠졌습니다. 경계값도 청크 경로로 보냅니다.
            logger.info(
                "청크 분할 화자 분리 적용",
                duration=round(audio_duration, 1),
                threshold=threshold_sec,
            )

            def _progress_cb(current: int, total: int) -> None:
                # 0.30 ~ 0.80 범위에서 청크별 진행률 업데이트
                progress = 0.30 + (current / total) * 0.50
                msg = f"화자 분리 처리 중... (청크 {current}/{total})"
                _update_task_status(task_id, TaskStatus.processing, progress, msg)

            # 청크 모드는 현재 num_speakers 힌트 미지원 (각 청크별 별도 추정)
            dia_segments = engine.diarize_chunked(
                wav_path,
                chunk_duration_sec=settings.dia_chunk_duration_minutes * 60,
                overlap_sec=settings.dia_chunk_overlap_seconds,
                progress_callback=_progress_cb,
            )
        else:
            # 15분 이하 → 기존 단일 파일 처리. REQ-DIA-PERF-001: max_speakers 힌트로 clustering 가속.
            # REQ-DIA-PERF-003: settings.dia_target_sample_rate > 0이면 다운샘플링 적용 (실험적).
            target_sr = (
                settings.dia_target_sample_rate if settings.dia_target_sample_rate > 0 else None
            )
            dia_segments = engine.diarize(
                wav_path,
                num_speakers=num_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                target_sample_rate=target_sr,
            )

        # --- 5단계: 매칭 (모드별 분기) ---
        if parallel_mode and not stt_segments:
            # 병렬 모드 + STT 결과 없음: 매칭 skip, raw 화자 segments만 반환
            # (minutes_task가 STT/DIA 결과를 결합하여 매칭 수행)
            _update_task_status(task_id, TaskStatus.processing, 0.85, "화자 segments 정리 중...")
            speaker_stats: dict[str, dict] = {}
            for dseg in dia_segments:
                sp = dseg.speaker_id
                if sp not in speaker_stats:
                    speaker_stats[sp] = {
                        "speaker_id": sp,
                        "total_speaking_time": 0.0,
                        "segment_count": 0,
                    }
                speaker_stats[sp]["total_speaking_time"] += dseg.end - dseg.start
                speaker_stats[sp]["segment_count"] += 1

            processing_end = datetime.now(UTC)
            final_result = {
                "task_id": task_id,
                "stt_task_id": stt_task_id,
                "status": TaskStatus.completed.value,
                # 매칭 전 raw segments (text 없음). minutes_task가 이를 보고 매칭 수행.
                "segments": [
                    {
                        "speaker_id": dseg.speaker_id,
                        "start": dseg.start,
                        "end": dseg.end,
                    }
                    for dseg in dia_segments
                ],
                "speakers": list(speaker_stats.values()),
                "num_speakers": len(speaker_stats),
                "matched": False,  # minutes_task가 매칭을 수행해야 함을 알림
                "created_at": processing_start.isoformat(),
                "completed_at": processing_end.isoformat(),
            }
        else:
            # 레거시 직렬 모드 (또는 병렬 모드인데 STT 결과까지 함께 받은 경우)
            _update_task_status(task_id, TaskStatus.processing, 0.80, "STT 결과와 화자 매칭 중...")
            matcher = SpeakerMatcher()
            diarized_segments = matcher.match(stt_segments, dia_segments)

            speaker_stats = {}
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
            final_result = {
                "task_id": task_id,
                "stt_task_id": stt_task_id,
                "status": TaskStatus.completed.value,
                "segments": [seg.model_dump() for seg in diarized_segments],
                "speakers": list(speaker_stats.values()),
                "num_speakers": len(speaker_stats),
                "matched": True,
                "created_at": processing_start.isoformat(),
                "completed_at": processing_end.isoformat(),
            }

        _cache_result(task_id, final_result)

        # DB 영속 저장 (best-effort, REQ-PERSIST-006)
        try:
            from backend.services.sync_service import persist_task_result

            persist_task_result(
                task_id=task_id,
                task_type="diarization",
                status="completed",
                result_data=final_result,
            )
        except Exception:
            pass  # DB 저장 실패는 무시 (Redis에 이미 저장됨)

        _update_task_status(task_id, TaskStatus.completed, 1.0, "화자 분리 완료")

        # SPEC-TONE-001: tone_model 설정 시 tone_task 트리거 (REQ-TONE-007)
        # tone_task의 finally가 DIA wav를 삭제하므로 tone 활성화 시 여기서 삭제하지 않는다.
        final_segments = cast(list[dict], final_result["segments"])
        if audio_path and settings.tone_model:
            _trigger_tone_task(
                dia_task_id=task_id,
                dia_wav_path=str(audio_path),
                segments=final_segments,
            )

        # BUGFIX: 병렬 모드에서는 diarized_segments 변수가 정의되지 않으므로
        # final_result["segments"]를 참조해야 두 분기 모두에서 안전하다.
        logger.info(
            "화자 분리 작업 완료",
            task_id=task_id,
            segments=len(final_segments),
            speakers=len(speaker_stats),
            matched=final_result.get("matched", True),
        )
        return final_result

    except SoftTimeLimitExceeded:
        # REQ-PERF-004: 시간 초과 시 실패 상태 기록 및 정리
        error_msg = "처리 시간이 60분을 초과하여 화자 분리가 중단되었습니다"
        logger.error("화자 분리 작업 시간 초과", task_id=task_id)
        _update_task_status(task_id, TaskStatus.failed, 0.0, error_message=error_msg)
        failed_result = {
            "task_id": task_id,
            "stt_task_id": stt_task_id,
            "status": "failed",
            "error": error_msg,
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)
        return failed_result

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
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.services.sync_service import persist_task_result

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
            "error_message": error_msg,
            "created_at": processing_start.isoformat(),
        }
        _cache_result(task_id, failed_result)

        # DB 영속 저장 - 실패 상태 (best-effort, REQ-PERSIST-007)
        try:
            from backend.services.sync_service import persist_task_result

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
        # 병렬 모드에서 STT가 만든 DIA 전용 WAV 사본({task_id}_dia.wav)은
        # DIA가 소유한다. STT는 이 파일을 삭제하지 않으므로(순차 실행 시 race 방지)
        # DIA 완료/실패 후 여기서 정리한다.
        # SPEC-TONE-001 (REQ-TONE-005): tone_model이 설정된 경우 DIA wav 삭제를
        # tone_task의 finally로 이연한다. tone 비활성화 시 기존 동작 유지 (AC-TONE-006).
        if audio_path and not settings.tone_model:
            try:
                Path(audio_path).unlink(missing_ok=True)
            except OSError:
                pass


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="diarization_task",
    soft_time_limit=3600,  # 60분 소프트 타임아웃 (개별 DIA Celery task 기준)
    time_limit=3900,  # 65분 하드 타임아웃
)
def diarization_celery_task(
    self,
    task_id: str,
    stt_task_id: str | None = None,
    num_speakers: int | None = None,
    min_speakers: int = 1,
    max_speakers: int = 10,
    audio_path: str | None = None,
) -> dict:
    """
    Celery 래퍼: diarization_task 호출 + 재시도 처리

    Args:
        task_id: 화자 분리 작업 UUID
        stt_task_id: STT 작업 UUID (병렬 모드에서는 선택)
        num_speakers: 예상 화자 수
        min_speakers: 최소 화자 수
        max_speakers: 최대 화자 수
        audio_path: WAV 파일 직접 경로 (병렬 모드)
    """
    try:
        return diarization_task(
            task_id=task_id,
            stt_task_id=stt_task_id,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            audio_path=audio_path,
        )
    except SoftTimeLimitExceeded:
        # 시간 초과 → 재시도 안 함 (diarization_task 내부에서 이미 처리)
        return {"task_id": task_id, "status": "failed", "error": "시간 초과"}
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
