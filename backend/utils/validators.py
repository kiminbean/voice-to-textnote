"""
오디오 파일 검증 유틸리티
REQ-STT-001, REQ-STT-003, REQ-STT-004 구현
"""

import ipaddress
import shutil
import socket
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, TypeAdapter, ValidationError

from backend.utils.file_signature import verify_file_signature
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_WEBHOOK_URL_ADAPTER = TypeAdapter(AnyHttpUrl)
_FORBIDDEN_WEBHOOK_HOSTS = {
    "localhost",
    "localhost.localdomain",
}

# 허용 오디오 형식 및 MIME 타입
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".ogg"}
ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/vorbis",
    "video/mp4",
}


def validate_audio_format(
    filename: str,
    content_type: str | None = None,
    file_header: bytes | None = None,
) -> tuple[bool, str]:
    """
    파일 확장자, MIME 타입, 매직 바이트 검증
    Returns: (is_valid, error_message)

    Args:
        filename: 파일명
        content_type: 클라이언트가 보고한 MIME 타입
        file_header: 파일의 첫 16바이트 (매직 바이트 검증용, None이면 생략)
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return False, (
            f"지원하지 않는 파일 형식입니다. 허용: WAV, MP3, M4A, MP4, OGG (받은 형식: {suffix})"
        )

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # content_type이 명시적으로 오디오가 아닌 경우만 거부
        if not content_type.startswith("audio/") and content_type != "application/octet-stream":
            return False, f"지원하지 않는 MIME 타입입니다: {content_type}"

    # REQ-SEC-040~043: 매직 바이트 검증
    if file_header is not None:
        if not verify_file_signature(file_header, suffix):
            return False, "파일 시그니처(매직 바이트)가 확장자와 일치하지 않습니다."

    return True, ""


def validate_file_size(file_size_bytes: int, max_size_bytes: int) -> tuple[bool, str]:
    """
    파일 크기 검증 (REQ-STT-003: 최대 500MB)
    Returns: (is_valid, error_message)
    """
    if file_size_bytes <= 0:
        return False, "빈 파일은 업로드할 수 없습니다."

    if file_size_bytes > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = file_size_bytes / (1024 * 1024)
        return False, (
            f"파일 크기가 제한({max_mb:.0f}MB)을 초과합니다. 실제 크기: {actual_mb:.1f}MB"
        )
    return True, ""


def check_ffmpeg_available() -> bool:
    """ffmpeg 설치 여부 확인"""
    return shutil.which("ffmpeg") is not None


def _is_forbidden_webhook_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """서버 내부망으로 향하는 웹훅 URL 차단 여부."""
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _assert_public_webhook_host(hostname: str, port: int | None, resolve_host: bool) -> None:
    normalized = hostname.strip().rstrip(".").lower()
    if normalized in _FORBIDDEN_WEBHOOK_HOSTS or normalized.endswith(".localhost"):
        raise ValueError("웹훅 URL은 localhost를 사용할 수 없습니다")

    try:
        literal_ip = ipaddress.ip_address(normalized.strip("[]"))
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_forbidden_webhook_ip(literal_ip):
            raise ValueError("웹훅 URL은 사설/로컬 네트워크 주소를 사용할 수 없습니다")
        return

    if not resolve_host:
        return

    try:
        addrinfo = socket.getaddrinfo(normalized, port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"웹훅 URL 호스트를 확인할 수 없습니다: {hostname}") from exc

    for entry in addrinfo:
        sockaddr = entry[4]
        ip_text = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if _is_forbidden_webhook_ip(resolved_ip):
            raise ValueError("웹훅 URL은 사설/로컬 네트워크로 해석될 수 없습니다")


def validate_webhook_url(
    value: object,
    *,
    resolve_host: bool = False,
    allow_http: bool = False,
) -> str:
    """
    웹훅 수신 URL을 검증하고 정규화한다.

    기본적으로 HTTPS URL만 허용한다. 테스트 또는 내부 도구에서 HTTP를 허용해야
    하는 경우 allow_http=True를 명시해야 한다. SSRF 방지를 위해 localhost/사설망/
    링크 로컬/예약 주소를 거부한다. resolve_host=True이면 실제 전송 직전에 DNS
    결과도 검사한다.
    """
    try:
        url = str(_WEBHOOK_URL_ADAPTER.validate_python(value))
    except ValidationError as exc:
        raise ValueError("웹훅 URL은 유효한 HTTP(S) URL이어야 합니다") from exc

    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("웹훅 URL은 유효한 HTTP(S) URL이어야 합니다")  # pragma: no cover
    if parsed.username or parsed.password:
        raise ValueError("웹훅 URL에는 사용자 정보를 포함할 수 없습니다")

    _assert_public_webhook_host(parsed.hostname, parsed.port, resolve_host)
    if parsed.scheme == "http" and not allow_http:
        raise ValueError("웹훅 URL은 HTTPS만 허용됩니다")
    return url
