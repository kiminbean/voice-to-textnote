"""
오디오 전처리 파이프라인
REQ-STT-015: 16kHz 모노 WAV 변환
REQ-STT-016: 오디오 레벨 정규화
REQ-STT-017: 손상 파일 감지
SPEC-AUDIO-PREP-001: 사용자 선택형 전처리 옵션 (high-pass, low-pass, 무음 트리밍)
"""

import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.silence import detect_nonsilent
from pydub.utils import mediainfo

from backend.utils.logger import get_logger

logger = get_logger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_DBFS = -20.0  # 정규화 목표 레벨

# SPEC-AUDIO-PREP-001: 전처리 옵션 기본값 및 안전 한계
DEFAULT_HIGH_PASS_HZ = 80  # 음성 대역 보존 (저주파 험/팬 노이즈 제거)
MAX_HIGH_PASS_HZ = 500
MIN_LOW_PASS_HZ = 1000
MAX_LOW_PASS_HZ = 16000
DEFAULT_SILENCE_THRESHOLD_DB = -40.0  # 이 아래는 무음으로 간주
DEFAULT_SILENCE_MIN_LEN_MS = 700  # 이 길이 이상 연속 무음 구간만 잘라냄


def convert_to_wav_16k(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """
    오디오를 16kHz 모노 WAV로 변환 (REQ-STT-015)
    output_path가 None이면 임시 파일 생성
    """
    input_path = Path(input_path)

    try:
        audio = AudioSegment.from_file(str(input_path))
    except CouldntDecodeError as e:
        raise ValueError(f"파일 손상 또는 지원되지 않는 오디오 코덱: {e}") from e
    except Exception as e:  # pragma: no cover
        raise ValueError(f"오디오 파일 디코딩 실패: {e}") from e

    # 모노 변환
    if audio.channels != TARGET_CHANNELS:
        audio = audio.set_channels(TARGET_CHANNELS)

    # 샘플레이트 변환
    if audio.frame_rate != TARGET_SAMPLE_RATE:
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = Path(tmp.name)
        tmp.close()
    else:
        output_path = Path(output_path)

    audio.export(str(output_path), format="wav")
    logger.info("오디오 변환 완료", input=str(input_path), output=str(output_path))
    return output_path


def normalize_audio(audio: AudioSegment, target_dbfs: float = TARGET_DBFS) -> AudioSegment:
    """
    오디오 레벨 정규화 (REQ-STT-016)
    무음 오디오의 경우 변경 없이 반환
    """
    if audio.dBFS == float("-inf"):
        # 무음 오디오 - 정규화 불가
        logger.warning("무음 오디오 감지됨, 정규화 생략")
        return audio

    change_db = target_dbfs - audio.dBFS
    return audio.apply_gain(change_db)


def convert_and_normalize(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """변환 + 정규화를 한 번에 처리"""
    input_path = Path(input_path)

    try:
        audio = AudioSegment.from_file(str(input_path))
    except CouldntDecodeError as e:
        raise ValueError(f"파일 손상 또는 지원되지 않는 오디오 코덱: {e}") from e
    except Exception as e:  # pragma: no cover
        raise ValueError(f"오디오 파일 디코딩 실패: {e}") from e

    # 모노 + 16kHz 변환
    audio = audio.set_channels(TARGET_CHANNELS).set_frame_rate(TARGET_SAMPLE_RATE)

    # 정규화
    audio = normalize_audio(audio)

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = Path(tmp.name)
        tmp.close()
    else:
        output_path = Path(output_path)  # pragma: no cover

    audio.export(str(output_path), format="wav")
    logger.info(
        "오디오 변환+정규화 완료",
        input=str(input_path),
        output=str(output_path),
        duration_ms=len(audio),
    )
    return output_path


def get_audio_duration_seconds(file_path: str | Path) -> float:
    """오디오 재생 시간(초) 반환"""
    path = Path(file_path)

    try:
        # BUGFIX: 업로드 검증/화자 분리 임계값 확인 단계에서 전체 오디오를 메모리에
        # 올리면 긴 파일에서 불필요한 메모리 사용이 커집니다. WAV는 헤더만 읽고,
        # 그 외 포맷은 mediainfo(ffprobe) 우선으로 길이를 계산해 전체 로드를 피합니다.
        if path.suffix.lower() == ".wav":
            with wave.open(str(path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                if frame_rate <= 0:
                    raise ValueError("유효하지 않은 WAV 샘플레이트")
                return wav_file.getnframes() / float(frame_rate)

        info = mediainfo(str(path))
        duration_str = info.get("duration")
        if duration_str:
            return float(duration_str)

        audio = AudioSegment.from_file(str(path))
        return len(audio) / 1000.0
    except Exception as e:
        raise ValueError(f"오디오 재생 시간 측정 실패: {e}") from e


def cleanup_temp_file(file_path: str | Path) -> None:
    """임시 파일 안전 삭제 (REQ-STT-004, REQ-STT-014)"""
    path = Path(file_path)
    if path.exists():
        os.unlink(path)
        logger.info("임시 파일 삭제", path=str(path))


# ---------------------------------------------------------------------------
# SPEC-AUDIO-PREP-001: 사용자 선택형 전처리 옵션
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocessOptions:
    """오디오 전처리 옵션 묶음.

    모든 필드는 선택적이며, False/None이면 해당 단계는 건너뜁니다.
    """

    convert_to_16k_mono: bool = True
    normalize: bool = True
    target_dbfs: float = TARGET_DBFS
    high_pass_hz: int | None = None  # 예: 80 → 80Hz 미만 차단
    low_pass_hz: int | None = None  # 예: 8000 → 8000Hz 초과 차단
    trim_silence: bool = False
    silence_threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB
    silence_min_len_ms: int = DEFAULT_SILENCE_MIN_LEN_MS

    def validate(self) -> None:
        """옵션 안전 범위 검증. 위반 시 ValueError."""
        if self.high_pass_hz is not None:
            if not (1 <= self.high_pass_hz <= MAX_HIGH_PASS_HZ):
                raise ValueError(f"high_pass_hz는 1~{MAX_HIGH_PASS_HZ}Hz 사이여야 합니다.")
        if self.low_pass_hz is not None:
            if not (MIN_LOW_PASS_HZ <= self.low_pass_hz <= MAX_LOW_PASS_HZ):
                raise ValueError(
                    f"low_pass_hz는 {MIN_LOW_PASS_HZ}~{MAX_LOW_PASS_HZ}Hz 사이여야 합니다."
                )
        if not (-60.0 <= self.target_dbfs <= 0.0):
            raise ValueError("target_dbfs는 -60.0 ~ 0.0 범위여야 합니다.")
        if self.silence_min_len_ms < 100:
            raise ValueError("silence_min_len_ms는 100ms 이상이어야 합니다.")


def trim_leading_trailing_silence(
    audio: AudioSegment,
    silence_threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB,
    min_silence_len_ms: int = DEFAULT_SILENCE_MIN_LEN_MS,
) -> AudioSegment:
    """오디오 앞/뒤의 무음 구간을 제거하고 발화 구간만 남깁니다.

    내부 무음(말 사이 정상적 휴지)은 보존하기 위해 detect_nonsilent를 사용해
    첫 발화 시작 ~ 마지막 발화 종료까지만 잘라냅니다.
    """
    if len(audio) == 0:
        return audio

    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len_ms,
        silence_thresh=silence_threshold_db,
    )

    if not nonsilent_ranges:
        # 발화가 감지되지 않으면 원본 유지 (사용자가 의도한 침묵일 수 있음)
        return audio

    start_ms = nonsilent_ranges[0][0]
    end_ms = nonsilent_ranges[-1][1]
    return audio[start_ms:end_ms]


def _apply_preprocess_options(audio: AudioSegment, options: PreprocessOptions) -> AudioSegment:
    """검증된 PreprocessOptions를 AudioSegment에 순차 적용."""
    if options.convert_to_16k_mono:
        if audio.channels != TARGET_CHANNELS:
            audio = audio.set_channels(TARGET_CHANNELS)
        if audio.frame_rate != TARGET_SAMPLE_RATE:
            audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)

    if options.high_pass_hz is not None:
        audio = audio.high_pass_filter(options.high_pass_hz)

    if options.low_pass_hz is not None:
        audio = audio.low_pass_filter(options.low_pass_hz)

    if options.trim_silence:
        audio = trim_leading_trailing_silence(
            audio,
            silence_threshold_db=options.silence_threshold_db,
            min_silence_len_ms=options.silence_min_len_ms,
        )

    if options.normalize:
        audio = normalize_audio(audio, target_dbfs=options.target_dbfs)

    return audio


def preprocess_audio(
    input_path: str | Path,
    options: PreprocessOptions | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """옵션 기반 오디오 전처리 파이프라인.

    실행 순서: (16kHz 모노 변환) → high-pass → low-pass → silence trim → normalize.
    output_path가 None이면 임시 WAV 파일을 생성합니다.
    손상된 파일이나 잘못된 옵션은 ValueError로 보고됩니다.
    """
    opts = options or PreprocessOptions()
    opts.validate()

    input_path = Path(input_path)

    try:
        audio = AudioSegment.from_file(str(input_path))
    except CouldntDecodeError as e:
        raise ValueError(f"파일 손상 또는 지원되지 않는 오디오 코덱: {e}") from e
    except Exception as e:  # noqa: BLE001 - pydub은 다양한 예외를 던짐
        raise ValueError(f"오디오 파일 디코딩 실패: {e}") from e

    audio = _apply_preprocess_options(audio, opts)

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = Path(tmp.name)
        tmp.close()
    else:
        output_path = Path(output_path)

    audio.export(str(output_path), format="wav")
    logger.info(
        "오디오 전처리 완료",
        input=str(input_path),
        output=str(output_path),
        duration_ms=len(audio),
        high_pass_hz=opts.high_pass_hz,
        low_pass_hz=opts.low_pass_hz,
        trim_silence=opts.trim_silence,
        normalize=opts.normalize,
    )
    return output_path
