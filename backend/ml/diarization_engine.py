"""
pyannote.audio 화자 분리 엔진 래퍼 - 싱글톤 패턴
REQ-DIA-007: pyannote/speaker-diarization-3.1 모델 사용
REQ-DIA-008: 지연 로딩 (lazy load) + 싱글톤 재사용
REQ-DIA-009: CPU only 처리
REQ-DIA-010: HuggingFace 토큰 인증
REQ-DIA-011: 서버 시작 시 사전 로드 (warm-up)
"""

import time
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from backend.pipeline.speaker_matcher import SpeakerSegment
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# pyannote.audio는 런타임에만 임포트 (mock 테스트 지원)
if TYPE_CHECKING:
    pass


class DiarizationEngine:
    """
    pyannote.audio 싱글톤 화자 분리 엔진
    - 프로세스당 1개 인스턴스
    - 스레드 안전 초기화 (double-checked locking)
    - CPU only 실행
    """

    _instance: "DiarizationEngine | None" = None
    _lock: Lock = Lock()

    _model_loaded: bool = False
    _load_time_seconds: float | None = None
    _model_name: str = "pyannote/speaker-diarization-3.1"
    _pipeline: Any = None

    def __init__(self) -> None:
        pass

    @classmethod
    def get_instance(cls) -> "DiarizationEngine":
        """싱글톤 인스턴스 반환 (스레드 안전, double-checked locking)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load(self, hf_token: str | None = None, model_name: str | None = None) -> None:
        """
        pyannote Pipeline 로드 (REQ-DIA-008: lazy load + 재사용)
        이미 로드된 경우 즉시 반환

        Args:
            hf_token: HuggingFace 접근 토큰 (필수)
            model_name: 사용할 모델 ID (기본: pyannote/speaker-diarization-3.1)

        Raises:
            ValueError: HuggingFace 토큰 미제공 시
            RuntimeError: 모델 로드 실패 시
        """
        if self._model_loaded:
            logger.info("화자 분리 모델 이미 로드됨, 재사용", model=self._model_name)
            return

        with self._lock:
            if self._model_loaded:
                return

            # HuggingFace 토큰 검증 (REQ-DIA-010)
            if not hf_token:
                raise ValueError(
                    "HuggingFace 토큰이 필요합니다. "
                    "HUGGINGFACE_TOKEN 환경 변수를 설정하거나 hf_token 인자를 제공하세요."
                )

            if model_name:
                self._model_name = model_name

            logger.info("화자 분리 모델 로드 시작", model=self._model_name)
            start_time = time.time()

            try:
                # pyannote.audio Pipeline 로드
                from pyannote.audio import Pipeline  # type: ignore[import]

                pipeline = Pipeline.from_pretrained(
                    self._model_name,
                    use_auth_token=hf_token,
                )

                self._pipeline = pipeline
                self._load_time_seconds = time.time() - start_time
                self._model_loaded = True

                logger.info(
                    "화자 분리 모델 로드 완료",
                    model=self._model_name,
                    load_time_seconds=round(self._load_time_seconds, 2),
                )

            except ImportError as e:
                logger.error("pyannote.audio 미설치", error=str(e))
                raise RuntimeError(
                    "pyannote.audio 패키지가 설치되지 않았습니다. "
                    "'pip install pyannote-audio>=3.1.0'으로 설치하세요."
                ) from e
            except Exception as e:
                logger.error("화자 분리 모델 로드 실패", error=str(e))
                raise RuntimeError(f"화자 분리 모델 로드 실패: {e}") from e

    def diarize(self, audio_path: str | Path) -> list[SpeakerSegment]:
        """
        오디오 파일 화자 분리 실행 (REQ-DIA-009)

        Args:
            audio_path: WAV 파일 경로 (16kHz 모노 권장)

        Returns:
            SpeakerSegment 리스트 (speaker_id, start, end)

        Raises:
            RuntimeError: 모델 미로드 또는 분리 실패 시
        """
        if not self._model_loaded or self._pipeline is None:
            raise RuntimeError("화자 분리 모델이 로드되지 않았습니다. load()를 먼저 호출하세요.")

        logger.info("화자 분리 시작", path=str(audio_path))
        start_time = time.time()

        try:
            # Pipeline 실행 (CPU only, REQ-DIA-009)
            diarization = self._pipeline(str(audio_path))

            # itertracks() 결과를 SpeakerSegment 리스트로 변환
            segments: list[SpeakerSegment] = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    SpeakerSegment(
                        speaker_id=speaker,
                        start=round(turn.start, 3),
                        end=round(turn.end, 3),
                    )
                )

            elapsed = time.time() - start_time
            logger.info(
                "화자 분리 완료",
                path=str(audio_path),
                segments=len(segments),
                elapsed_seconds=round(elapsed, 2),
            )

            return segments

        except Exception as e:
            logger.error("화자 분리 실패", error=str(e), path=str(audio_path))
            raise

    def unload(self) -> None:
        """모델 메모리 해제"""
        with self._lock:
            self._pipeline = None
            self._model_loaded = False
            self._load_time_seconds = None
            logger.info("화자 분리 모델 언로드 완료")

    @property
    def is_loaded(self) -> bool:
        return self._model_loaded

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def load_time_seconds(self) -> float | None:
        return self._load_time_seconds
