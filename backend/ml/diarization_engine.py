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

    # REQ-DIA-PERF-002: Silero VAD 사전 필터 (회의 무음 구간 제거)
    _vad_model: Any = None
    _vad_loaded: bool = False

    # VAD 통합 상수
    # - segment 간 silence padding: pyannote가 segment boundary를 인식하도록 보장
    # - 너무 짧으면 segment 연속 처리 / 너무 길면 압축 효과 감소
    VAD_SILENCE_PAD_SEC: float = 0.5
    # - silero get_speech_timestamps의 무음 임계 (이보다 짧은 무음은 발화로 간주)
    VAD_MIN_SILENCE_MS: int = 500
    # - 각 음성 구간 양쪽 padding (boundary 정확도 향상)
    VAD_SPEECH_PAD_MS: int = 200

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

    def _load_vad(self) -> Any:
        """Silero VAD 모델 lazy load (싱글톤 캐싱)"""
        if self._vad_loaded and self._vad_model is not None:
            return self._vad_model

        with self._lock:
            if self._vad_loaded and self._vad_model is not None:
                return self._vad_model

            try:
                from silero_vad import load_silero_vad

                logger.info("Silero VAD 모델 로드 시작")
                vad_start = time.time()
                self._vad_model = load_silero_vad()
                self._vad_loaded = True
                logger.info(
                    "Silero VAD 모델 로드 완료",
                    load_time_seconds=round(time.time() - vad_start, 2),
                )
                return self._vad_model
            except ImportError as e:
                logger.warning("silero-vad 미설치, VAD 사전 필터 비활성화", error=str(e))
                return None
            except Exception as e:
                logger.warning("Silero VAD 로드 실패, VAD 사전 필터 비활성화", error=str(e))
                return None

    def _compress_with_vad(
        self,
        waveform: Any,
        sample_rate: int,
    ) -> tuple[Any, list[dict]]:
        """Silero VAD로 음성 구간만 추출하고 segment 사이에 silence padding 삽입

        Args:
            waveform: torch.Tensor (channels, samples)
            sample_rate: 샘플레이트 (Hz)

        Returns:
            (compressed_waveform, mapping_list)
            - compressed_waveform: torch.Tensor — 음성+silence padding으로 구성된 새 waveform
            - mapping_list: 각 음성 구간의 (compressed_start_sample, compressed_end_sample,
              original_start_sample)을 보관해 역매핑에 사용

        VAD 실패/패키지 미설치/음성 없음 시 빈 mapping 반환 (호출자가 원본 사용 결정).
        """
        import torch

        vad_model = self._load_vad()
        if vad_model is None:
            return waveform, []

        try:
            from silero_vad import get_speech_timestamps

            # silero_vad는 mono 1D 텐서를 기대
            mono_waveform = waveform.squeeze() if waveform.dim() > 1 else waveform

            speech_ts = get_speech_timestamps(
                mono_waveform,
                vad_model,
                sampling_rate=sample_rate,
                min_silence_duration_ms=self.VAD_MIN_SILENCE_MS,
                speech_pad_ms=self.VAD_SPEECH_PAD_MS,
            )

            if not speech_ts:
                logger.warning("VAD: 음성 구간 없음, 원본 waveform 사용")
                return waveform, []

            # 음성 구간 사이에 silence padding 삽입 (pyannote가 boundary 인식하도록)
            silence_samples = int(sample_rate * self.VAD_SILENCE_PAD_SEC)
            channels = waveform.shape[0] if waveform.dim() > 1 else 1
            silence_chunk = torch.zeros((channels, silence_samples))

            chunks: list[Any] = []
            mapping: list[dict] = []
            cumulative = 0

            for i, ts in enumerate(speech_ts):
                if i > 0:
                    chunks.append(silence_chunk)
                    cumulative += silence_samples

                # 양 채널 모두 보존
                if waveform.dim() > 1:
                    seg_wav = waveform[:, ts["start"]:ts["end"]]
                else:
                    seg_wav = waveform[ts["start"]:ts["end"]].unsqueeze(0)

                seg_length = ts["end"] - ts["start"]
                mapping.append(
                    {
                        "compressed_start": cumulative,
                        "compressed_end": cumulative + seg_length,
                        "original_start": ts["start"],
                    }
                )
                chunks.append(seg_wav)
                cumulative += seg_length

            compressed = torch.cat(chunks, dim=1)
            original_duration = waveform.shape[-1] / sample_rate
            compressed_duration = compressed.shape[-1] / sample_rate
            logger.info(
                "VAD 압축 완료",
                speech_segments=len(speech_ts),
                original_seconds=round(original_duration, 2),
                compressed_seconds=round(compressed_duration, 2),
                ratio=round(compressed_duration / original_duration, 3) if original_duration > 0 else 0,
            )
            return compressed, mapping
        except Exception as e:
            logger.warning("VAD 처리 실패, 원본 waveform 사용", error=str(e))
            return waveform, []

    def _map_segments(
        self,
        raw_segments: list[SpeakerSegment],
        mapping: list[dict],
        sample_rate: int,
    ) -> list[SpeakerSegment]:
        """compressed 시간의 segment를 원본 시간으로 역매핑

        한 segment가 silence padding을 가로질러 여러 mapping에 걸칠 수 있으므로,
        각 mapping에서 겹치는 부분만 잘라 별도 segment로 생성한다.
        """
        if not mapping:
            return raw_segments

        mapped: list[SpeakerSegment] = []
        for seg in raw_segments:
            seg_start_sample = int(seg.start * sample_rate)
            seg_end_sample = int(seg.end * sample_rate)

            for m in mapping:
                # 이 mapping과 겹치는 구간 계산
                overlap_start = max(seg_start_sample, m["compressed_start"])
                overlap_end = min(seg_end_sample, m["compressed_end"])
                if overlap_end <= overlap_start:
                    continue

                offset_start = overlap_start - m["compressed_start"]
                offset_end = overlap_end - m["compressed_start"]
                orig_start_sample = m["original_start"] + offset_start
                orig_end_sample = m["original_start"] + offset_end

                mapped.append(
                    SpeakerSegment(
                        speaker_id=seg.speaker_id,
                        start=round(orig_start_sample / sample_rate, 3),
                        end=round(orig_end_sample / sample_rate, 3),
                    )
                )

        # 같은 화자의 인접 segment 병합 (silence padding으로 인한 작은 끊김 제거)
        return self._merge_adjacent_segments(mapped)

    def diarize(
        self,
        audio_path: str | Path,
        num_speakers: int | None = None,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
        vad_filter: bool = True,
    ) -> list[SpeakerSegment]:
        """
        오디오 파일 화자 분리 실행 (REQ-DIA-009)

        Args:
            audio_path: WAV 파일 경로 (16kHz 모노 권장)
            num_speakers: 정확한 화자 수가 알려져 있을 때 명시 (clustering 강제)
            min_speakers: 화자 수 하한 (자동 추정 범위 제한)
            max_speakers: 화자 수 상한 (REQ-DIA-PERF-001:
                회의록 앱 default=4로 clustering 후보를 줄여 10~20% 가속 기대)
            vad_filter: REQ-DIA-PERF-002 — True면 Silero VAD로 무음 구간을 사전에 제거해
                pyannote 입력을 줄인다. 회의 무음 비율(보통 30~50%) 만큼 가속.

        Returns:
            SpeakerSegment 리스트 (speaker_id, start, end)

        Raises:
            RuntimeError: 모델 미로드 또는 분리 실패 시
        """
        if not self._model_loaded or self._pipeline is None:
            raise RuntimeError("화자 분리 모델이 로드되지 않았습니다. load()를 먼저 호출하세요.")

        logger.info(
            "화자 분리 시작",
            path=str(audio_path),
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            vad_filter=vad_filter,
        )
        start_time = time.time()
        waveform = None
        compressed = None
        result = None

        try:
            # torchaudio로 오디오 로드 (torchcodec 의존성 우회)
            import torch
            import torchaudio

            waveform, sample_rate = torchaudio.load(str(audio_path))

            # VAD 사전 필터링 (선택)
            mapping: list[dict] = []
            if vad_filter:
                compressed, mapping = self._compress_with_vad(waveform, sample_rate)
            else:
                compressed = waveform

            # 화자 수 hint 구성: num_speakers 우선, 없으면 min/max 범위
            pipeline_kwargs: dict = {}
            if num_speakers is not None:
                pipeline_kwargs["num_speakers"] = num_speakers
            else:
                if min_speakers is not None:
                    pipeline_kwargs["min_speakers"] = min_speakers
                if max_speakers is not None:
                    pipeline_kwargs["max_speakers"] = max_speakers

            # BUGFIX: 긴 CPU 추론에서 gradient 추적이 남으면 메모리 사용량이 불필요하게
            # 커질 수 있습니다. inference_mode로 감싸고 추론 후 참조를 즉시 해제합니다.
            with torch.inference_mode():
                result = self._pipeline(
                    {"waveform": compressed, "sample_rate": sample_rate},
                    **pipeline_kwargs,
                )

            raw_segments = self._segments_from_result(result)

            # VAD 압축을 적용했으면 원본 timestamp로 역매핑
            segments = (
                self._map_segments(raw_segments, mapping, sample_rate)
                if mapping
                else raw_segments
            )

            elapsed = time.time() - start_time
            logger.info(
                "화자 분리 완료",
                path=str(audio_path),
                segments=len(segments),
                elapsed_seconds=round(elapsed, 2),
                vad_applied=bool(mapping),
            )

            return segments

        except Exception as e:
            logger.error("화자 분리 실패", error=str(e), path=str(audio_path))
            raise
        finally:
            waveform = None
            compressed = None
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
