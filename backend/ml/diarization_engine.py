"""
pyannote.audio 화자 분리 엔진 래퍼 - 싱글톤 패턴
REQ-DIA-007: pyannote/speaker-diarization-3.1 모델 사용
REQ-DIA-008: 지연 로딩 (lazy load) + 싱글톤 재사용
REQ-DIA-009: CPU only 처리
REQ-DIA-010: HuggingFace 토큰 인증
REQ-DIA-011: 서버 시작 시 사전 로드 (warm-up)
"""

import gc
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
        waveform = None
        result = None

        try:
            # torchaudio로 오디오 로드 (torchcodec 의존성 우회)
            import torch
            import torchaudio

            waveform, sample_rate = torchaudio.load(str(audio_path))

            # BUGFIX: 긴 CPU 추론에서 gradient 추적이 남으면 메모리 사용량이 불필요하게
            # 커질 수 있습니다. inference_mode로 감싸고 추론 후 참조를 즉시 해제합니다.
            with torch.inference_mode():
                result = self._pipeline({"waveform": waveform, "sample_rate": sample_rate})

            segments = self._segments_from_result(result)

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
        finally:
            waveform = None
            result = None
            gc.collect()

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

        import torch
        import torchaudio

        logger.info(
            "청크 분할 화자 분리 시작",
            path=str(audio_path),
            chunk_sec=chunk_duration_sec,
            overlap_sec=overlap_sec,
        )
        start_time = time.time()

        audio_info = torchaudio.info(str(audio_path))
        sample_rate = audio_info.sample_rate
        total_samples = audio_info.num_frames
        total_duration_sec = total_samples / sample_rate

        chunk_samples = chunk_duration_sec * sample_rate
        overlap_samples = overlap_sec * sample_rate

        if total_samples <= 0:
            logger.warning("비어 있는 오디오 파일", path=str(audio_path))
            return []

        # 청크 분할 계획 수립
        chunks: list[tuple[int, int]] = []  # (start_sample, end_sample)
        pos = 0
        while pos < total_samples:
            end = min(pos + chunk_samples + overlap_samples, total_samples)
            chunks.append((pos, end))
            pos += chunk_samples

        total_chunks = len(chunks)
        logger.info(
            "청크 수",
            total_chunks=total_chunks,
            total_duration=round(total_duration_sec, 1),
        )

        all_segments: list[SpeakerSegment] = []
        global_speaker_count = 0

        for i, (chunk_start, chunk_end) in enumerate(chunks):
            chunk_waveform = None
            result = None
            chunk_offset_sec = chunk_start / sample_rate
            overlap_threshold_sec = overlap_sec if i > 0 else 0

            logger.info("청크 처리 중", chunk=i + 1, total=total_chunks)

            try:
                # BUGFIX: 기존 구현은 torchaudio.load()로 전체 waveform을 한 번에 메모리에
                # 올린 뒤 슬라이싱해서 긴 파일에서 OOM 위험이 있었습니다. 각 청크만 부분
                # 로드해 pyannote 입력으로 넘기면 긴 오디오에서도 메모리 상한이 고정됩니다.
                chunk_waveform, _ = torchaudio.load(
                    str(audio_path),
                    frame_offset=chunk_start,
                    num_frames=chunk_end - chunk_start,
                )

                with torch.inference_mode():
                    result = self._pipeline({"waveform": chunk_waveform, "sample_rate": sample_rate})

                local_segments = self._segments_from_result(result)

                local_to_global = self._match_chunk_speakers(
                    local_segments=local_segments,
                    previous_segments=all_segments,
                    chunk_offset_sec=chunk_offset_sec,
                    overlap_sec=overlap_sec,
                )

                chunk_segments: list[SpeakerSegment] = []
                for local_seg in local_segments:
                    global_speaker_id = local_to_global.get(local_seg.speaker_id)
                    if global_speaker_id is None:
                        global_speaker_id = f"SPEAKER_{global_speaker_count:02d}"
                        local_to_global[local_seg.speaker_id] = global_speaker_id
                        global_speaker_count += 1

                    # BUGFIX: 이전 구현은 start < overlap_sec인 세그먼트를 통째로 버려서
                    # 경계에 걸친 발화의 뒷부분까지 잃었습니다. 오버랩 구간만 잘라내고
                    # 그 이후 구간은 유지해야 STT와의 매칭이 끊기지 않습니다.
                    trimmed_start = max(local_seg.start, overlap_threshold_sec)
                    if local_seg.end <= trimmed_start:
                        continue

                    chunk_segments.append(
                        SpeakerSegment(
                            speaker_id=global_speaker_id,
                            start=round(chunk_offset_sec + trimmed_start, 3),
                            end=round(chunk_offset_sec + local_seg.end, 3),
                        )
                    )

                all_segments.extend(chunk_segments)

                # 진행률 콜백 호출
                if progress_callback:
                    progress_callback(i + 1, total_chunks)

                logger.info("청크 완료", chunk=i + 1, segments=len(chunk_segments))
            finally:
                chunk_waveform = None
                result = None
                gc.collect()

        elapsed = time.time() - start_time
        merged_segments = self._merge_adjacent_segments(all_segments)
        logger.info(
            "청크 분할 화자 분리 완료",
            total_segments=len(merged_segments),
            elapsed_seconds=round(elapsed, 2),
        )

        return merged_segments

    @staticmethod
    def _segments_from_result(result: Any) -> list[SpeakerSegment]:
        """pyannote 출력 객체를 SpeakerSegment 리스트로 정규화"""
        diarization = getattr(result, "speaker_diarization", result)

        segments: list[SpeakerSegment] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(
                SpeakerSegment(
                    speaker_id=speaker,
                    start=round(turn.start, 3),
                    end=round(turn.end, 3),
                )
            )
        return segments

    @staticmethod
    def _calc_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
        overlap_start = max(a_start, b_start)
        overlap_end = min(a_end, b_end)
        return max(0.0, overlap_end - overlap_start)

    @classmethod
    def _match_chunk_speakers(
        cls,
        local_segments: list[SpeakerSegment],
        previous_segments: list[SpeakerSegment],
        chunk_offset_sec: float,
        overlap_sec: int,
    ) -> dict[str, str]:
        """오버랩 구간의 실제 시간 겹침으로 현재 청크 화자를 이전 글로벌 ID에 매핑"""
        if chunk_offset_sec <= 0 or not previous_segments:
            return {}

        overlap_window_start = chunk_offset_sec
        overlap_window_end = chunk_offset_sec + overlap_sec
        previous_overlap_segments = [
            seg
            for seg in previous_segments
            if seg.end > overlap_window_start and seg.start < overlap_window_end
        ]
        if not previous_overlap_segments:
            return {}

        candidate_pairs: list[tuple[float, float, str, str]] = []
        for local_seg in local_segments:
            local_overlap_start = max(local_seg.start, 0.0)
            local_overlap_end = min(local_seg.end, float(overlap_sec))
            if local_overlap_end <= local_overlap_start:
                continue

            global_overlap_start = chunk_offset_sec + local_overlap_start
            global_overlap_end = chunk_offset_sec + local_overlap_end
            for previous_seg in previous_overlap_segments:
                overlap = cls._calc_overlap(
                    global_overlap_start,
                    global_overlap_end,
                    previous_seg.start,
                    previous_seg.end,
                )
                if overlap > 0:
                    candidate_pairs.append(
                        (
                            overlap,
                            previous_seg.start,
                            local_seg.speaker_id,
                            previous_seg.speaker_id,
                        )
                    )

        candidate_pairs.sort(key=lambda item: (-item[0], item[1]))

        matched: dict[str, str] = {}
        used_global_speakers: set[str] = set()
        for _, _, local_speaker_id, global_speaker_id in candidate_pairs:
            if local_speaker_id in matched or global_speaker_id in used_global_speakers:
                continue
            matched[local_speaker_id] = global_speaker_id
            used_global_speakers.add(global_speaker_id)

        return matched

    @staticmethod
    def _merge_adjacent_segments(
        segments: list[SpeakerSegment],
        tolerance_sec: float = 0.05,
    ) -> list[SpeakerSegment]:
        """같은 화자의 인접/중첩 세그먼트를 병합해 청크 경계 아티팩트를 줄임"""
        if not segments:
            return []

        sorted_segments = sorted(segments, key=lambda seg: (seg.start, seg.end, seg.speaker_id))
        merged = [sorted_segments[0]]
        for segment in sorted_segments[1:]:
            previous = merged[-1]
            if (
                segment.speaker_id == previous.speaker_id
                and segment.start <= previous.end + tolerance_sec
            ):
                merged[-1] = SpeakerSegment(
                    speaker_id=previous.speaker_id,
                    start=previous.start,
                    end=round(max(previous.end, segment.end), 3),
                )
                continue
            merged.append(segment)
        return merged

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
