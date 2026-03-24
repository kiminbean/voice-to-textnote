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
                    token=hf_token,
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
            # torchaudio로 오디오 로드 (torchcodec 의존성 우회)
            import torchaudio
            waveform, sample_rate = torchaudio.load(str(audio_path))

            # Pipeline 실행 (메모리 기반 입력, REQ-DIA-009)
            result = self._pipeline({"waveform": waveform, "sample_rate": sample_rate})

            # pyannote 4.x: DiarizeOutput → .speaker_diarization으로 Annotation 추출
            diarization = getattr(result, "speaker_diarization", result)

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

    def diarize_chunked(
        self,
        audio_path: str | Path,
        chunk_duration_sec: int = 600,
        overlap_sec: int = 30,
        progress_callback: Any = None,
    ) -> list[SpeakerSegment]:
        """
        REQ-PERF-001: 긴 오디오를 청크 단위로 화자 분리 후 결과 병합

        Args:
            audio_path: WAV 파일 경로
            chunk_duration_sec: 청크 길이 (초, 기본 600=10분)
            overlap_sec: 청크 간 오버랩 (초, 기본 30)
            progress_callback: 청크 완료 시 호출 (current_chunk, total_chunks)

        Returns:
            SpeakerSegment 리스트 (글로벌 타임스탬프 기준)
        """
        if not self._model_loaded or self._pipeline is None:
            raise RuntimeError("화자 분리 모델이 로드되지 않았습니다.")

        import torchaudio

        logger.info("청크 분할 화자 분리 시작", path=str(audio_path),
                     chunk_sec=chunk_duration_sec, overlap_sec=overlap_sec)
        start_time = time.time()

        waveform, sample_rate = torchaudio.load(str(audio_path))
        total_samples = waveform.shape[1]
        total_duration_sec = total_samples / sample_rate

        chunk_samples = chunk_duration_sec * sample_rate
        overlap_samples = overlap_sec * sample_rate

        # 청크 분할 계획 수립
        chunks: list[tuple[int, int]] = []  # (start_sample, end_sample)
        pos = 0
        while pos < total_samples:
            end = min(pos + chunk_samples + overlap_samples, total_samples)
            chunks.append((pos, end))
            pos += chunk_samples

        total_chunks = len(chunks)
        logger.info("청크 수", total_chunks=total_chunks,
                     total_duration=round(total_duration_sec, 1))

        all_segments: list[SpeakerSegment] = []
        # 청크 간 스피커 ID 매핑 (오버랩 구간 타임스탬프 기반)
        speaker_remap: dict[str, str] = {}
        global_speaker_count = 0

        for i, (chunk_start, chunk_end) in enumerate(chunks):
            chunk_waveform = waveform[:, chunk_start:chunk_end]
            chunk_offset_sec = chunk_start / sample_rate
            overlap_threshold_sec = (overlap_sec if i > 0 else 0)

            logger.info("청크 처리 중", chunk=i + 1, total=total_chunks)

            # 청크별 화자 분리 실행
            result = self._pipeline({"waveform": chunk_waveform, "sample_rate": sample_rate})
            diarization = getattr(result, "speaker_diarization", result)

            chunk_segments: list[SpeakerSegment] = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                # 오버랩 구간 중복 제거: 첫 청크 이후, 오버랩 영역 시작 부분 세그먼트 건너뜀
                if i > 0 and turn.start < overlap_threshold_sec:
                    continue

                # 청크 로컬 스피커 ID를 글로벌 ID로 매핑
                local_key = f"chunk{i}_{speaker}"
                if local_key not in speaker_remap:
                    # 이전 청크의 오버랩 구간에서 동일 화자 탐색 (타임스탬프 기반)
                    matched = False
                    if i > 0 and all_segments:
                        seg_global_start = chunk_offset_sec + turn.start
                        for prev_seg in reversed(all_segments[-20:]):
                            # 이전 세그먼트와 시간적으로 근접하면 동일 화자로 간주
                            if abs(prev_seg.end - seg_global_start) < overlap_sec:
                                speaker_remap[local_key] = prev_seg.speaker_id
                                matched = True
                                break
                    if not matched:
                        speaker_remap[local_key] = f"SPEAKER_{global_speaker_count:02d}"
                        global_speaker_count += 1

                global_start = chunk_offset_sec + turn.start
                global_end = chunk_offset_sec + turn.end

                chunk_segments.append(
                    SpeakerSegment(
                        speaker_id=speaker_remap[local_key],
                        start=round(global_start, 3),
                        end=round(global_end, 3),
                    )
                )

            all_segments.extend(chunk_segments)

            # 진행률 콜백 호출
            if progress_callback:
                progress_callback(i + 1, total_chunks)

            logger.info("청크 완료", chunk=i + 1, segments=len(chunk_segments))

        elapsed = time.time() - start_time
        logger.info("청크 분할 화자 분리 완료",
                     total_segments=len(all_segments),
                     elapsed_seconds=round(elapsed, 2))

        return all_segments

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
