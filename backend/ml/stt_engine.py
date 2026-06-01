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

# mlx-community 모델명 → faster-whisper 모델명 매핑
# (faster-whisper는 OpenAI 모델명을 동일하게 사용하지만 turbo는 large-v3-turbo)
_MLX_TO_FASTER_MODEL_MAP = {
    "mlx-community/whisper-tiny-mlx": "tiny",
    "mlx-community/whisper-base-mlx": "base",
    "mlx-community/whisper-small-mlx": "small",
    "mlx-community/whisper-medium-mlx": "medium",
    "mlx-community/whisper-large-v3-turbo": "large-v3-turbo",
    "mlx-community/whisper-large-v3-mlx": "large-v3",
}


def _resolve_whisper_model(model_name: str) -> str:
    """mlx-community 모델명을 openai-whisper 모델명으로 변환"""
    return _MLX_TO_WHISPER_MODEL_MAP.get(model_name, model_name)


def _resolve_faster_whisper_model(model_name: str) -> str:
    """mlx-community 모델명을 faster-whisper 모델명으로 변환"""
    return _MLX_TO_FASTER_MODEL_MAP.get(model_name, model_name)


class WhisperEngine:
    """
    플랫폼 적응형 Whisper 싱글톤 엔진
    - macOS: mlx_whisper 사용 (Apple Silicon 가속)
    - Linux: faster-whisper 우선 (CTranslate2 int8 - CPU에서 4~6배 빠름), 미설치 시 openai-whisper 폴백
    - 프로세스당 1개 인스턴스
    - 스레드 안전 초기화
    """

    _instance: "WhisperEngine | None" = None
    _lock: Lock = Lock()

    _model_loaded: bool = False
    _load_time_seconds: float | None = None
    _model_name: str = MLX_DEFAULT_MODEL
    _device: str = "cpu"
    _backend: str = "unknown"  # "mlx", "faster_whisper", 또는 "whisper"
    _whisper_model: Any = None  # openai-whisper 모델 객체
    _faster_whisper_model: Any = None  # faster-whisper WhisperModel 객체

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

            # 플랫폼별 백엔드 선택 (우선순위: MLX → faster-whisper → openai-whisper)
            if self._try_load_mlx():
                pass  # MLX 로드 성공 (macOS Apple Silicon)
            elif self._try_load_faster_whisper():
                pass  # faster-whisper 로드 성공 (CPU int8 또는 CUDA)
            elif self._try_load_whisper():
                pass  # openai-whisper 로드 성공 (최후의 폴백)
            else:
                raise RuntimeError(
                    "STT 백엔드를 찾을 수 없습니다. "
                    "macOS: 'pip install mlx-whisper>=0.4.3', "
                    "Linux: 'pip install faster-whisper>=1.0.0' (권장) "
                    "또는 'pip install openai-whisper'로 설치하세요."
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

    def _try_load_faster_whisper(self) -> bool:
        """faster-whisper 백엔드 로드 시도 (CPU int8 또는 CUDA, 빠름)

        REQ-STT-PERF-001: CPU에서 openai-whisper 대비 약 4~6배 빠름
        (CTranslate2 int8 양자화 + VAD 필터링)
        """
        try:
            from faster_whisper import WhisperModel

            # CUDA 가용성 확인 → 없으면 CPU int8
            try:
                import torch

                cuda_available = torch.cuda.is_available()
            except ImportError:
                cuda_available = False

            if cuda_available:
                device = "cuda"
                compute_type = "float16"
            else:
                device = "cpu"
                compute_type = "int8"  # CPU에서 양자화로 추가 가속

            # mlx 모델명 → faster-whisper 모델명
            fw_model_name = _resolve_faster_whisper_model(self._model_name)

            logger.info(
                "faster-whisper 모델 로드 중",
                model=fw_model_name,
                device=device,
                compute_type=compute_type,
            )
            self._faster_whisper_model = WhisperModel(
                fw_model_name,
                device=device,
                compute_type=compute_type,
            )
            self._device = device
            self._backend = "faster_whisper"
            logger.info(
                "faster-whisper 백엔드 선택",
                device=device,
                compute_type=compute_type,
            )
            return True
        except ImportError:
            logger.info("faster-whisper 미설치, 다음 백엔드 시도")
            return False
        except Exception as e:
            logger.error("faster-whisper 로드 실패", error=str(e))
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
        initial_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        STT 추론 실행 (REQ-STT-005, REQ-STT-008)

        Args:
            audio_path: 오디오 파일 경로
            language: 전사 언어 코드 (기본: "ko")
            initial_prompt: Whisper 프롬프트 — 어휘/스펠링 힌트 (REQ-VOCAB-001)

        Returns:
            dict with keys: text, segments, language
            segments: list of {id, start, end, text, avg_logprob, ...}
        """
        if not self._model_loaded:
            self.load()

        self._check_memory_usage()

        logger.info("STT 추론 시작", path=str(audio_path), language=language, backend=self._backend,
                     has_initial_prompt=initial_prompt is not None)
        start_time = time.time()

        try:
            if self._backend == "mlx":
                result = self._transcribe_mlx(audio_path, language, initial_prompt)
            elif self._backend == "faster_whisper":
                result = self._transcribe_faster_whisper(audio_path, language, initial_prompt)
            else:
                result = self._transcribe_whisper(audio_path, language, initial_prompt)

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

    def _transcribe_mlx(
        self, audio_path: str | Path, language: str, initial_prompt: str | None = None,
    ) -> dict[str, Any]:
        """MLX 백엔드 추론"""
        import mlx_whisper

        kwargs: dict[str, Any] = dict(
            path_or_hf_repo=self._model_name,
            language=language,
            word_timestamps=True,
        )
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        return mlx_whisper.transcribe(str(audio_path), **kwargs)

    def _transcribe_whisper(
        self, audio_path: str | Path, language: str, initial_prompt: str | None = None,
    ) -> dict[str, Any]:
        """openai-whisper 백엔드 추론"""
        kwargs: dict[str, Any] = dict(
            language=language,
            word_timestamps=True,
        )
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        result = self._whisper_model.transcribe(str(audio_path), **kwargs)
        return result

    def _transcribe_faster_whisper(
        self, audio_path: str | Path, language: str, initial_prompt: str | None = None,
    ) -> dict[str, Any]:
        """faster-whisper 백엔드 추론

        openai-whisper와 호환되는 형식으로 결과를 반환한다.
        - word_timestamps=False: 단어 단위 타임스탬프는 필요 없으므로 비활성화 (약 20% 가속)
        - beam_size=1: greedy decoding (속도 우선, small 모델은 정확도 차이 미미)
        - vad_filter=True: Silero VAD로 무음 구간 제거 (정확도/속도 향상)
        """
        kwargs: dict[str, Any] = dict(
            language=language,
            word_timestamps=False,
            beam_size=1,
            vad_filter=True,
        )
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        segments_gen, info = self._faster_whisper_model.transcribe(
            str(audio_path),
            **kwargs,
        )

        # generator → list (info 객체의 일부 필드는 소비 후 확정됨)
        segments_list = list(segments_gen)

        segments = []
        for i, seg in enumerate(segments_list):
            segments.append(
                {
                    "id": i,
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": seg.text,
                    "avg_logprob": (
                        float(seg.avg_logprob) if seg.avg_logprob is not None else None
                    ),
                    "no_speech_prob": (
                        float(seg.no_speech_prob)
                        if seg.no_speech_prob is not None
                        else None
                    ),
                    "compression_ratio": (
                        float(seg.compression_ratio)
                        if seg.compression_ratio is not None
                        else None
                    ),
                }
            )

        text = " ".join(seg["text"].strip() for seg in segments).strip()

        return {
            "text": text,
            "segments": segments,
            "language": info.language if info else language,
        }

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
