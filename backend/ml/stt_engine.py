"""
mlx-whisper / openai-whisper STT 엔진 래퍼 - 싱글톤 패턴
REQ-STT-005: whisper 모델 + language="ko"
REQ-STT-006: MLX Apple Silicon 가속 (MPS), CPU/CUDA 폴백
REQ-STT-007: 지연 로딩 (lazy load) + 재사용
REQ-STT-021: 서버 시작 시 사전 로드 (warm-up)
REQ-STT-022: 메모리 사용량 모니터링

플랫폼별 백엔드:
  - macOS (Apple Silicon): mlx_whisper 사용
  - Linux/기타: openai-whisper 사용 (CPU/CUDA)
"""

import platform
import time
from pathlib import Path
from threading import Lock
from typing import Any

import psutil

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 메모리 경고 임계값: 24GB * 80% = 19.2GB (bytes)
MEMORY_WARNING_THRESHOLD_BYTES = 19 * 1024 * 1024 * 1024

# 플랫폼별 기본 모델명
MLX_DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
WHISPER_DEFAULT_MODEL = "small"

# mlx-community 모델명 → openai-whisper 모델명 매핑
_MLX_TO_WHISPER_MODEL_MAP = {
    "mlx-community/whisper-tiny-mlx": "tiny",
    "mlx-community/whisper-base-mlx": "base",
    "mlx-community/whisper-small-mlx": "small",
    "mlx-community/whisper-medium-mlx": "medium",
    "mlx-community/whisper-large-v3-turbo": "turbo",
    "mlx-community/whisper-large-v3-mlx": "large-v3",
}


def _resolve_whisper_model(model_name: str) -> str:
    """mlx-community 모델명을 openai-whisper 모델명으로 변환"""
    return _MLX_TO_WHISPER_MODEL_MAP.get(model_name, model_name)


class WhisperEngine:
    """
    플랫폼 적응형 Whisper 싱글톤 엔진
    - macOS: mlx_whisper 사용 (Apple Silicon 가속)
    - Linux: openai-whisper 사용 (CPU/CUDA)
    - 프로세스당 1개 인스턴스
    - 스레드 안전 초기화
    """

    _instance: "WhisperEngine | None" = None
    _lock: Lock = Lock()

    _model_loaded: bool = False
    _load_time_seconds: float | None = None
    _model_name: str = MLX_DEFAULT_MODEL
    _device: str = "cpu"
    _backend: str = "unknown"  # "mlx" 또는 "whisper"
    _whisper_model: Any = None  # openai-whisper 모델 객체

    def __init__(self) -> None:
        pass

    @classmethod
    def get_instance(cls) -> "WhisperEngine":
        """싱글톤 인스턴스 반환 (스레드 안전)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load(self, model_name: str | None = None) -> None:
        """
        모델 로드 (REQ-STT-007: lazy load + 재사용)
        이미 로드된 경우 즉시 반환
        플랫폼에 따라 mlx_whisper 또는 openai-whisper 사용
        """
        if self._model_loaded:
            logger.info("모델 이미 로드됨, 재사용", model=self._model_name)
            return

        with self._lock:
            if self._model_loaded:
                return

            if model_name:
                self._model_name = model_name

            logger.info("모델 로드 시작", model=self._model_name)
            start_time = time.time()

            # 플랫폼별 백엔드 선택
            if self._try_load_mlx():
                pass  # MLX 로드 성공
            elif self._try_load_whisper():
                pass  # openai-whisper 로드 성공
            else:
                raise RuntimeError(
                    "STT 백엔드를 찾을 수 없습니다. "
                    "macOS: 'pip install mlx-whisper>=0.4.3', "
                    "Linux: 'pip install openai-whisper'로 설치하세요."
                )

            self._load_time_seconds = time.time() - start_time
            self._model_loaded = True

            logger.info(
                "모델 로드 완료",
                model=self._model_name,
                backend=self._backend,
                device=self._device,
                load_time_seconds=round(self._load_time_seconds, 2),
            )

    def _try_load_mlx(self) -> bool:
        """MLX 백엔드 로드 시도 (macOS Apple Silicon)"""
        if platform.system() != "Darwin":
            return False

        try:
            import mlx_whisper  # noqa: F401

            self._device = self._detect_device()
            self._backend = "mlx"
            logger.info("MLX 백엔드 선택", device=self._device)
            return True
        except ImportError:
            logger.info("mlx_whisper 미설치, 다른 백엔드 시도")
            return False

    def _try_load_whisper(self) -> bool:
        """openai-whisper 백엔드 로드 시도 (CPU/CUDA)"""
        try:
            import whisper

            # mlx 모델명을 openai-whisper 모델명으로 변환
            whisper_model_name = _resolve_whisper_model(self._model_name)

            # CUDA 가용성 확인
            import torch
            if torch.cuda.is_available():
                self._device = "cuda"
            else:
                self._device = "cpu"

            logger.info(
                "openai-whisper 모델 로드 중",
                model=whisper_model_name,
                device=self._device,
            )
            self._whisper_model = whisper.load_model(whisper_model_name, device=self._device)
            self._backend = "whisper"
            logger.info("openai-whisper 백엔드 선택", device=self._device)
            return True
        except ImportError:
            logger.info("openai-whisper 미설치")
            return False
        except Exception as e:
            logger.error("openai-whisper 로드 실패", error=str(e))
            return False

    def transcribe(
        self,
        audio_path: str | Path,
        language: str = "ko",
    ) -> dict[str, Any]:
        """
        STT 추론 실행 (REQ-STT-005, REQ-STT-008)

        Returns:
            dict with keys: text, segments, language
            segments: list of {id, start, end, text, avg_logprob, ...}
        """
        if not self._model_loaded:
            self.load()

        self._check_memory_usage()

        logger.info("STT 추론 시작", path=str(audio_path), language=language, backend=self._backend)
        start_time = time.time()

        try:
            if self._backend == "mlx":
                result = self._transcribe_mlx(audio_path, language)
            else:
                result = self._transcribe_whisper(audio_path, language)

            elapsed = time.time() - start_time
            segment_count = len(result.get("segments", []))

            logger.info(
                "STT 추론 완료",
                elapsed_seconds=round(elapsed, 2),
                segments=segment_count,
                language=result.get("language", language),
                backend=self._backend,
            )

            return result

        except Exception as e:
            logger.error("STT 추론 실패", error=str(e), path=str(audio_path))
            raise

    def _transcribe_mlx(self, audio_path: str | Path, language: str) -> dict[str, Any]:
        """MLX 백엔드 추론"""
        import mlx_whisper

        return mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=self._model_name,
            language=language,
            word_timestamps=True,
        )

    def _transcribe_whisper(self, audio_path: str | Path, language: str) -> dict[str, Any]:
        """openai-whisper 백엔드 추론"""
        result = self._whisper_model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
        )
        return result

    @property
    def is_loaded(self) -> bool:
        return self._model_loaded

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def load_time_seconds(self) -> float | None:
        return self._load_time_seconds

    @property
    def backend(self) -> str:
        return self._backend

    def get_memory_info(self) -> dict[str, float]:
        """현재 메모리 사용량 반환 (REQ-STT-022)"""
        vm = psutil.virtual_memory()
        return {
            "total_mb": vm.total / (1024 * 1024),
            "available_mb": vm.available / (1024 * 1024),
            "used_mb": vm.used / (1024 * 1024),
            "percent": vm.percent,
        }

    def _check_memory_usage(self) -> None:
        """메모리 임계값 초과 시 경고 로그 (REQ-STT-022)"""
        vm = psutil.virtual_memory()
        if vm.used > MEMORY_WARNING_THRESHOLD_BYTES:
            logger.warning(
                "메모리 사용량 경고: 임계값 초과",
                used_gb=round(vm.used / (1024**3), 2),
                threshold_gb=round(MEMORY_WARNING_THRESHOLD_BYTES / (1024**3), 2),
                percent=vm.percent,
            )

    @staticmethod
    def _detect_device() -> str:
        """Apple Silicon MPS 가용성 확인 (REQ-STT-006)"""
        try:
            import mlx.core as mx

            _ = mx.array([1.0])
            logger.info("MLX Apple Silicon 가속 사용 가능")
            return "mps"
        except ImportError:
            logger.warning("MLX 미설치, CPU로 폴백")
            return "cpu"
        except Exception as e:
            logger.warning("MLX 초기화 실패, CPU로 폴백", error=str(e))
            return "cpu"
