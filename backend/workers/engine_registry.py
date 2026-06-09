"""
AC-DI-012: Celery Worker용 엔진 레지스트리

Celery worker는 FastAPI Request context가 없으므로 module-level 싱글톤을 사용합니다.
Worker 프로세스 시작 시 한 번만 초기화되어 재사용됩니다.
"""

from threading import Lock

from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Module-level singleton instances (Celery worker 전용)
_worker_whisper_engine: WhisperEngine | None = None
_worker_whisper_lock = Lock()

_worker_diarization_engine: DiarizationEngine | None = None
_worker_diarization_lock = Lock()


def get_worker_whisper_engine() -> WhisperEngine:
    """Celery worker용 WhisperEngine 싱글톤 반환 (스레드 안전)"""
    global _worker_whisper_engine

    if _worker_whisper_engine is None:
        with _worker_whisper_lock:
            if _worker_whisper_engine is None:
                logger.info("Celery Worker: WhisperEngine 초기화")
                _worker_whisper_engine = WhisperEngine()
    return _worker_whisper_engine


def get_worker_diarization_engine() -> DiarizationEngine:
    """Celery worker용 DiarizationEngine 싱글톤 반환 (스레드 안전)"""
    global _worker_diarization_engine

    if _worker_diarization_engine is None:
        with _worker_diarization_lock:
            if _worker_diarization_engine is None:
                logger.info("Celery Worker: DiarizationEngine 초기화")
                _worker_diarization_engine = DiarizationEngine()
    return _worker_diarization_engine
