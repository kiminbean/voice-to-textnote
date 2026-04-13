"""
오디오 전처리 파이프라인
REQ-STT-015: 16kHz 모노 WAV 변환
REQ-STT-016: 오디오 레벨 정규화
REQ-STT-017: 손상 파일 감지
"""

import os
import tempfile
import wave
from pathlib import Path

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.utils import mediainfo

from backend.utils.logger import get_logger

logger = get_logger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_DBFS = -20.0  # 정규화 목표 레벨


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
    except Exception as e:
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
    except Exception as e:
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
        output_path = Path(output_path)

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
