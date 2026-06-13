"""
backend/utils/validators.py 단위 테스트
오디오 포맷, 파일 크기, 웹훅 URL 검증
"""

import ipaddress
from unittest.mock import patch

import pytest

from backend.utils.validators import (
    _assert_public_webhook_host,
    _is_forbidden_webhook_ip,
    check_ffmpeg_available,
    validate_audio_format,
    validate_file_size,
    validate_webhook_url,
)


class TestValidateAudioFormat:
    """오디오 파일 확장자 및 MIME 타입 검증"""

    def test_valid_wav(self):
        ok, msg = validate_audio_format("test.wav")
        assert ok is True
        assert msg == ""

    def test_valid_mp3_with_mime(self):
        ok, _msg = validate_audio_format("song.mp3", "audio/mpeg")
        assert ok is True

    def test_valid_m4a(self):
        ok, _ = validate_audio_format("recording.m4a")
        assert ok is True

    def test_valid_ogg(self):
        ok, _ = validate_audio_format("voice.ogg")
        assert ok is True

    def test_invalid_extension(self):
        ok, msg = validate_audio_format("doc.pdf")
        assert ok is False
        assert "지원하지 않는 파일 형식" in msg

    def test_invalid_extension_txt(self):
        ok, msg = validate_audio_format("notes.txt")
        assert ok is False
        assert ".txt" in msg

    def test_invalid_mime_type(self):
        ok, msg = validate_audio_format("test.wav", "text/plain")
        assert ok is False
        assert "지원하지 않는 MIME" in msg

    def test_application_octet_stream_allowed(self):
        # application/octet-stream은 예외적으로 허용
        ok, _msg = validate_audio_format("test.wav", "application/octet-stream")
        assert ok is True

    def test_no_mime_type_passes(self):
        ok, _msg = validate_audio_format("test.mp3", None)
        assert ok is True

    def test_audio_mime_allowed(self):
        ok, _ = validate_audio_format("test.mp3", "audio/mpeg")
        assert ok is True


class TestValidateFileSize:
    """파일 크기 검증"""

    def test_valid_size(self):
        ok, msg = validate_file_size(1024, 500 * 1024 * 1024)
        assert ok is True
        assert msg == ""

    def test_empty_file(self):
        ok, msg = validate_file_size(0, 500 * 1024 * 1024)
        assert ok is False
        assert "빈 파일" in msg

    def test_negative_size(self):
        ok, _msg = validate_file_size(-1, 500 * 1024 * 1024)
        assert ok is False

    def test_oversized_file(self):
        max_bytes = 500 * 1024 * 1024
        ok, msg = validate_file_size(max_bytes + 1, max_bytes)
        assert ok is False
        assert "초과" in msg

    def test_exact_max_size_passes(self):
        max_bytes = 500 * 1024 * 1024
        ok, _ = validate_file_size(max_bytes, max_bytes)
        assert ok is True


class TestCheckFfmpegAvailable:
    """ffmpeg 설치 확인"""

    def test_returns_bool(self):
        result = check_ffmpeg_available()
        assert isinstance(result, bool)

    @patch("backend.utils.validators.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_available_when_found(self, mock_which):
        assert check_ffmpeg_available() is True

    @patch("backend.utils.validators.shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert check_ffmpeg_available() is False


class TestIsForbiddenWebhookIp:
    """내부망 IP 차단 여부"""

    def test_loopback_is_forbidden(self):
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("127.0.0.1")) is True

    def test_private_is_forbidden(self):
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("10.0.0.1")) is True
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("192.168.1.1")) is True
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("172.16.0.1")) is True

    def test_link_local_is_forbidden(self):
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("169.254.1.1")) is True

    def test_public_is_allowed(self):
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("8.8.8.8")) is False
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("1.1.1.1")) is False


class TestAssertPublicWebhookHost:
    """웹훅 호스트명 검증"""

    def test_localhost_blocked(self):
        with pytest.raises(ValueError, match="localhost"):
            _assert_public_webhook_host("localhost", None, False)

    def test_localhost_subdomain_blocked(self):
        with pytest.raises(ValueError, match="localhost"):
            _assert_public_webhook_host("app.localhost", None, False)

    def test_literal_private_ip_blocked(self):
        with pytest.raises(ValueError, match="사설"):
            _assert_public_webhook_host("10.0.0.1", None, False)

    def test_literal_loopback_blocked(self):
        with pytest.raises(ValueError):
            _assert_public_webhook_host("127.0.0.1", None, False)

    def test_public_hostname_passes_without_resolve(self):
        # resolve_host=False면 DNS 조회 없이 통과
        _assert_public_webhook_host("example.com", None, False)

    @patch("backend.utils.validators.socket.getaddrinfo")
    def test_resolve_to_private_raises(self, mock_getaddr):
        mock_getaddr.return_value = [(2, 1, 6, "", ("10.0.0.1", 443))]
        with pytest.raises(ValueError, match="사설/로컬"):
            _assert_public_webhook_host("evil.example.com", 443, True)

    @patch("backend.utils.validators.socket.getaddrinfo")
    def test_resolve_to_public_passes(self, mock_getaddr):
        mock_getaddr.return_value = [(2, 1, 6, "", ("93.184.216.34", 443))]
        _assert_public_webhook_host("example.com", 443, True)

    @patch("backend.utils.validators.socket.getaddrinfo", side_effect=OSError("dns fail"))
    def test_dns_failure_raises(self, mock_getaddr):
        with pytest.raises(ValueError, match="확인할 수 없"):
            _assert_public_webhook_host("unreachable.test", 443, True)


class TestValidateWebhookUrl:
    """웹훅 URL 전체 검증"""

    def test_valid_https_url(self):
        result = validate_webhook_url("https://example.com/webhook")
        assert result == "https://example.com/webhook"

    def test_valid_http_url(self):
        result = validate_webhook_url("http://example.com/hook")
        assert "example.com" in result

    def test_invalid_scheme_rejected(self):
        with pytest.raises(ValueError):
            validate_webhook_url("ftp://example.com/webhook")

    def test_localhost_rejected(self):
        with pytest.raises(ValueError, match="localhost"):
            validate_webhook_url("https://localhost/webhook")

    def test_url_with_credentials_rejected(self):
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("https://user:pass@example.com/webhook")

    def test_non_url_string_rejected(self):
        with pytest.raises(ValueError):
            validate_webhook_url("not-a-url")

    def test_private_ip_rejected(self):
        with pytest.raises(ValueError, match="사설"):
            validate_webhook_url("https://10.0.0.1/webhook")
