"""
오디오 파일 검증 유틸리티
REQ-STT-001, REQ-STT-003, REQ-STT-004 구현
"""
import shutil
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 허용 오디오 형식 및 MIME 타입
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/vorbis",
}


def validate_audio_format(filename: str, content_type: str | None = None) -> tuple[bool, str]:
    """
    파일 확장자 및 MIME 타입 검증
    Returns: (is_valid, error_message)
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return False, (
            f"지원하지 않는 파일 형식입니다. 허용: WAV, MP3, M4A, OGG (받은 형식: {suffix})"
        )

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # content_type이 명시적으로 오디오가 아닌 경우만 거부
        if not content_type.startswith("audio/") and content_type != "application/octet-stream":
            return False, f"지원하지 않는 MIME 타입입니다: {content_type}"

    return True, ""


def validate_file_size(file_size_bytes: int, max_size_bytes: int) -> tuple[bool, str]:
    """
    파일 크기 검증 (REQ-STT-003: 최대 500MB)
    Returns: (is_valid, error_message)
    """
    if file_size_bytes > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = file_size_bytes / (1024 * 1024)
        return False, (
            f"파일 크기가 제한({max_mb:.0f}MB)을 초과합니다. "
            f"실제 크기: {actual_mb:.1f}MB"
        )
    return True, ""


def check_ffmpeg_available() -> bool:
    """ffmpeg 설치 여부 확인"""
    return shutil.which("ffmpeg") is not None
