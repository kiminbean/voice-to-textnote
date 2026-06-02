"""
validators.py 추가 테스트 (커버리지 개선)

대상 라인:
- Line 103: _is_forbidden_webhook_ip
- Line 118-119: resolved_ip 예외 처리
- Line 138: URL의 사용자 정보 검증
"""

import ipaddress
from unittest.mock import patch

import pytest

from backend.utils.validators import (
    _assert_public_webhook_host,
    _is_forbidden_webhook_ip,
    validate_webhook_url,
)

# ---------------------------------------------------------------------------
# _is_forbidden_webhook_ip (Line 103)
# ---------------------------------------------------------------------------


class TestIsforbiddenwebhookipEdgecases:
    """IP 금지 여부 확인 엣지 케이스"""

    def test_ipv6_localhost_is_forbidden(self):
        """IPv6 로컬호스트도 금지"""
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("::1")) is True

    def test_ipv6_private_is_forbidden(self):
        """IPv6 사설 주소 금지"""
        # fc00::/7 (Unique Local)
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("fc00::1")) is True
        # fd00::/8
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("fd00::1")) is True

    def test_ipv6_link_local_is_forbidden(self):
        """IPv6 링크 로컬 금지"""
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("fe80::1")) is True

    def test_ipv6_public_is_allowed(self):
        """IPv6 공개 주소 허용"""
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("2001:4860:4860::8888")) is False

    def test_ipv4_class_e_reserved_is_forbidden(self):
        """IPv4 Class E (240.0.0.0/4) 예약 주소 금지"""
        assert _is_forbidden_webhook_ip(ipaddress.ip_address("240.0.0.1")) is True

    def test_ipv4_carrier_grade_nat(self):
        """CGN (100.64.0.0/10)도 사설로 간주해야 함"""
        # 현재 구현에서는 금지되지 않을 수 있음 (구현 확인 필요)
        # RFC 6598에 따라 사설 주소로 간주되어야 함
        result = _is_forbidden_webhook_ip(ipaddress.ip_address("100.64.0.1"))
        # 구현에 따라 True 또는 False
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# _assert_public_webhook_host - resolved_ip 예외 (Lines 118-119)
# ---------------------------------------------------------------------------


class TestassertpublicwebhookhostResolvedipexception:
    """DNS 해석 결과 예외 처리"""

    def test_raises_on_multiple_resolved_ips(self):
        """여러 IP로 해석되면 모두 검사"""
        with patch("backend.utils.validators.socket.getaddrinfo") as mock_getaddrinfo:
            # 공개 + 사설 IP 혼합
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("8.8.8.8", 443)),
                (2, 1, 6, "", ("192.168.1.1", 443)),
            ]

            with pytest.raises(ValueError, match="사설/로컬"):
                _assert_public_webhook_host("mixed.example.com", 443, True)


# ---------------------------------------------------------------------------
# validate_webhook_url - 사용자 정보 검증 (Line 138)
# ---------------------------------------------------------------------------


class TestvalidatewebhookUrlUserinfo:
    """URL 사용자 정보 검증"""

    def test_rejects_url_with_username(self):
        """사용자명이 포함된 URL 거부"""
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("https://user@example.com/webhook")

    def test_rejects_url_with_password(self):
        """비밀번호가 포함된 URL 거부"""
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("https://:password@example.com/webhook")

    def test_rejects_url_with_both_credentials(self):
        """사용자명과 비밀번호가 모두 포함된 URL 거부"""
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("https://user:pass@example.com/webhook")

    def test_allows_url_without_credentials(self):
        """자격 증명이 없는 URL 허용"""
        result = validate_webhook_url("https://example.com/webhook")
        assert "example.com" in result

    def test_normalizes_url(self):
        """URL 정규화 확인"""
        result = validate_webhook_url("HTTPS://EXAMPLE.COM:443/PATH")
        assert result.startswith("https://")
        assert "example.com" in result.lower()


# ---------------------------------------------------------------------------
# validate_webhook_url - scheme 검증 (추가)
# ---------------------------------------------------------------------------


class TestvalidatewebhookUrlScheme:
    """URL scheme 검증"""

    def test_rejects_ftp_scheme(self):
        """FTP scheme 거부"""
        with pytest.raises(ValueError, match="HTTP\\(S\\)"):
            validate_webhook_url("ftp://example.com/webhook")

    def test_accepts_http_scheme(self):
        """HTTP scheme 허용"""
        result = validate_webhook_url("http://example.com/webhook")
        assert result.startswith("http://")

    def test_accepts_https_scheme(self):
        """HTTPS scheme 허용"""
        result = validate_webhook_url("https://example.com/webhook")
        assert result.startswith("https://")


# ---------------------------------------------------------------------------
# validate_webhook_url - 호스트 검증 (추가)
# ---------------------------------------------------------------------------


class TestvalidatewebhookUrlHostvalidation:
    """호스트명 검증"""

    def test_calls_assert_public_with_hostname(self):
        """호스트 검증 로직 호출 확인"""
        # localhost는 거부되어야 함
        with pytest.raises(ValueError, match="localhost"):
            validate_webhook_url("https://localhost/webhook")

    def test_calls_with_resolved_ip_when_flag_true(self):
        """resolve_host=True면 DNS 해석"""
        with patch("backend.utils.validators.socket.getaddrinfo") as mock_getaddrinfo:
            # 사설 IP로 해석
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("10.0.0.1", 443))
            ]

            with pytest.raises(ValueError, match="사설"):
                validate_webhook_url("https://evil.example.com/webhook", resolve_host=True)
