"""
파일 시그니처(매직 바이트) 검증 유틸리티
REQ-SEC-040~043: 파일 업로드 시 실제 파일 시그니처 검증

외부 의존성 없이 순수 Python으로 구현 — libmagic 시스템 의존성 회피.
"""

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 오디오 파일 시그니처 (매직 바이트)
# 각 엔트리: 확장자 -> [(offset, expected_bytes), ...]
_AUDIO_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    ".wav": [(0, b"RIFF"), (8, b"WAVE")],
    ".mp3": [(0, b"ID3"), (0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2")],
    ".m4a": [(4, b"ftyp")],
    ".mp4": [(4, b"ftyp")],
    ".ogg": [(0, b"OggS")],
}

# 템플릿 파일 시그니처
_TEMPLATE_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    ".pdf": [(0, b"%PDF")],
    ".docx": [(0, b"PK\x03\x04")],
}

# 모든 시그니처 통합
ALL_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    **_AUDIO_SIGNATURES,
    **_TEMPLATE_SIGNATURES,
}


def _check_signature_at_offset(file_header: bytes, offset: int, expected: bytes) -> bool:
    """특정 offset에서 시그니처가 일치하는지 확인."""
    end = offset + len(expected)
    if len(file_header) < end:
        return False
    return file_header[offset:end] == expected


def verify_file_signature(file_header: bytes, extension: str) -> bool:
    """
    파일 헤더(첫 N 바이트)와 확장자가 일치하는지 검증.

    Args:
        file_header: 파일의 첫 16바이트 (또는 그 이상)
        extension: 점을 포함한 확장자 (예: ".wav")

    Returns:
        True if signature matches, False otherwise.
        extension이 알려지지 않은 경우 True (다른 검증에 위임).
    """
    ext = extension.lower()
    signatures = ALL_SIGNATURES.get(ext)

    # 알려지지 않은 확장자는 시그니처 검증을 통과 (다른 검증에서 처리)
    if signatures is None:
        return True

    # OR 조건: 시그니처 목록 중 하나라도 매칭되면 통과
    for offset, expected in signatures:
        if _check_signature_at_offset(file_header, offset, expected):
            # WAV의 경우 RIFF + WAVE 두 조건을 모두 확인
            if ext == ".wav":
                riff_ok = _check_signature_at_offset(file_header, 0, b"RIFF")
                wave_ok = _check_signature_at_offset(file_header, 8, b"WAVE")
                return riff_ok and wave_ok
            return True

    logger.warning(
        "파일 시그니처 불일치",
        extension=ext,
        header_hex=file_header[:16].hex(),
    )
    return False


def get_required_header_size() -> int:
    """시그니처 검증에 필요한 최소 헤더 크기 반환."""
    return 16
