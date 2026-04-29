"""
SPEC-SEC-001 보안 헤더 미들웨어 단위 테스트
REQ-SEC-009: allow_methods를 GET, POST, DELETE로 제한
REQ-SEC-010: allow_origins 설정 가능
REQ-SEC-011: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection 헤더 추가
REQ-SEC-012: 모든 보안 설정은 환경 변수/.env 파일로 관리
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_security_headers():
    """보안 헤더 미들웨어가 적용된 테스트 앱"""
    from backend.app.middleware.security_headers import SecurityHeadersMiddleware

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    return TestClient(app)


# ---------------------------------------------------------------------------
# REQ-SEC-011: 보안 헤더 검증
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """보안 헤더 응답 검증 테스트"""

    def test_x_content_type_options_header_present(self, app_with_security_headers):
        """REQ-SEC-011: X-Content-Type-Options 헤더 포함"""
        response = app_with_security_headers.get("/test")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_x_frame_options_header_present(self, app_with_security_headers):
        """REQ-SEC-011: X-Frame-Options 헤더 포함"""
        response = app_with_security_headers.get("/test")
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] in ("DENY", "SAMEORIGIN")

    def test_x_xss_protection_header_present(self, app_with_security_headers):
        """REQ-SEC-011: X-XSS-Protection 헤더 포함"""
        response = app_with_security_headers.get("/test")
        assert "x-xss-protection" in response.headers
        assert "1" in response.headers["x-xss-protection"]

    def test_security_headers_present_on_all_responses(self, app_with_security_headers):
        """REQ-SEC-011: 모든 응답에 보안 헤더 포함"""
        # GET 요청
        response = app_with_security_headers.get("/test")
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert "x-xss-protection" in response.headers

    def test_security_headers_on_404_response(self):
        """REQ-SEC-011: 404 응답에도 보안 헤더 포함"""
        from backend.app.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)

        response = client.get("/nonexistent", follow_redirects=False)
        assert "x-content-type-options" in response.headers


# ---------------------------------------------------------------------------
# REQ-SEC-009: CORS allow_methods 제한
# ---------------------------------------------------------------------------


class TestCorsMethodRestriction:
    """CORS 메서드 제한 테스트"""

    def test_cors_allows_get_method(self):
        """REQ-SEC-009: GET 메서드 허용"""
        from backend.app.config import Settings

        # Settings에 cors_allow_methods 확인
        settings = Settings.model_construct(
            api_keys=[],
            cors_allow_origins=["http://localhost:3000"],
            rate_limit_per_minute=60,
        )
        # GET이 허용 메서드에 포함
        assert "GET" in settings.cors_allow_methods

    def test_cors_allows_post_method(self):
        """REQ-SEC-009: POST 메서드 허용"""
        from backend.app.config import Settings

        settings = Settings.model_construct(
            api_keys=[],
            cors_allow_origins=["http://localhost:3000"],
            rate_limit_per_minute=60,
        )
        assert "POST" in settings.cors_allow_methods

    def test_cors_allows_delete_method(self):
        """REQ-SEC-009: DELETE 메서드 허용"""
        from backend.app.config import Settings

        settings = Settings.model_construct(
            api_keys=[],
            cors_allow_origins=["http://localhost:3000"],
            rate_limit_per_minute=60,
        )
        assert "DELETE" in settings.cors_allow_methods

    def test_cors_does_not_use_wildcard_methods(self):
        """REQ-SEC-009: CORS 메서드에 와일드카드(*) 사용 금지"""
        from backend.app.config import Settings

        settings = Settings.model_construct(
            api_keys=[],
            cors_allow_origins=["http://localhost:3000"],
            rate_limit_per_minute=60,
        )
        assert "*" not in settings.cors_allow_methods


# ---------------------------------------------------------------------------
# REQ-SEC-010: CORS allow_origins 설정 가능
# ---------------------------------------------------------------------------


class TestCorsOriginsConfig:
    """CORS Origins 설정 검증 테스트"""

    def test_cors_origins_configurable_via_settings(self):
        """REQ-SEC-010: allow_origins를 설정으로 관리"""
        from backend.app.config import Settings

        settings = Settings.model_construct(
            api_keys=[],
            cors_allow_origins=["http://localhost:3000", "http://localhost:8080"],
            rate_limit_per_minute=60,
        )
        assert "http://localhost:3000" in settings.cors_allow_origins
        assert "http://localhost:8080" in settings.cors_allow_origins

    def test_cors_origins_default_value_is_localhost(self):
        """REQ-SEC-010: 기본 Origins는 로컬호스트"""
        with patch.dict("os.environ", {}, clear=True):
            from backend.app.config import Settings

            # default_factory 필드는 .default가 Undefined이므로
            # 인스턴스를 생성해서 기본값 확인
            s = Settings()
            default_origins = s.cors_allow_origins
            assert any("localhost" in str(origin) for origin in default_origins)


# ---------------------------------------------------------------------------
# REQ-SEC-012: 보안 설정 환경 변수 관리
# ---------------------------------------------------------------------------


class TestSecurityConfiguration:
    """보안 설정 환경 변수 관리 테스트"""

    def test_api_keys_configurable_via_env(self):
        """REQ-SEC-012: API_KEYS 환경 변수로 설정 가능 (JSON 배열 형식)"""
        import json

        with patch.dict("os.environ", {"API_KEYS": json.dumps(["key1", "key2", "key3"])}):
            from backend.app.config import Settings

            # Settings가 API_KEYS 환경 변수를 읽어야 함
            s = Settings()
            assert "key1" in s.api_keys
            assert "key2" in s.api_keys
            assert "key3" in s.api_keys

    def test_rate_limit_configurable_via_env(self):
        """REQ-SEC-012: RATE_LIMIT_PER_MINUTE 환경 변수로 설정 가능"""
        from backend.app.config import Settings

        # Settings 클래스에 rate_limit_per_minute 필드가 있어야 함
        assert "rate_limit_per_minute" in Settings.model_fields

    def test_cors_origins_configurable_via_env(self):
        """REQ-SEC-012: CORS_ALLOW_ORIGINS 환경 변수로 설정 가능"""
        from backend.app.config import Settings

        # Settings 클래스에 cors_allow_origins 필드가 있어야 함
        assert "cors_allow_origins" in Settings.model_fields

    def test_security_settings_have_sensible_defaults(self):
        """REQ-SEC-012: 보안 설정의 기본값이 안전해야 함"""
        from backend.app.config import Settings

        # 기본 rate limit이 합리적인 값
        default_rate_limit = Settings.model_fields["rate_limit_per_minute"].default
        assert default_rate_limit is not None
        assert default_rate_limit >= 10  # 너무 낮으면 실용적이지 않음
        assert default_rate_limit <= 1000  # 너무 높으면 보안 위협
