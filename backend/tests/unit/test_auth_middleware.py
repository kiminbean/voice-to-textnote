"""
SPEC-SEC-001 API Key 인증 미들웨어 단위 테스트
REQ-SEC-001: 보호된 엔드포인트는 X-API-Key 헤더 전용 인증
REQ-SEC-002: 누락/잘못된 API Key → 401 반환
REQ-SEC-003: 유효한 API Key → 정상 처리
REQ-SEC-004: API_KEYS 미설정 시 인증 비활성화 (개발 모드)
REQ-SEC-005: API Key 평문 로그 금지
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def test_app_with_auth():
    """
    API Key 인증이 활성화된 테스트 앱 픽스처
    API_KEYS 환경 변수에 테스트 키 주입
    """
    from fastapi import Depends

    from backend.app.middleware.auth import verify_api_key

    app = FastAPI()

    @app.get("/protected")
    async def protected_route(api_key: str = Depends(verify_api_key)):
        return {"message": "ok", "authenticated": True}

    @app.get("/health")
    async def health_route():
        return {"status": "ok"}  # pragma: no cover

    with patch("backend.app.middleware.auth.settings") as mock_settings:
        mock_settings.api_keys = ["test-valid-key-123", "another-valid-key"]
        yield TestClient(app)


@pytest.fixture
def test_app_no_auth():
    """
    API Key 인증이 비활성화된 테스트 앱 픽스처 (API_KEYS 미설정)
    """
    from fastapi import Depends

    from backend.app.middleware.auth import verify_api_key

    app = FastAPI()

    @app.get("/protected")
    async def protected_route(api_key: str = Depends(verify_api_key)):
        return {"message": "ok", "authenticated": True}

    with patch("backend.app.middleware.auth.settings") as mock_settings:
        mock_settings.api_keys = []  # 빈 목록 = 인증 비활성화
        yield TestClient(app)


# ---------------------------------------------------------------------------
# REQ-SEC-001: 보호된 엔드포인트 접근 요구사항
# ---------------------------------------------------------------------------


class TestApiKeyHeaderAuth:
    """X-API-Key 헤더를 통한 API Key 인증 테스트"""

    def test_valid_api_key_via_header_returns_200(self, test_app_with_auth):
        """REQ-SEC-003: 유효한 X-API-Key 헤더 → 200 정상 처리"""
        response = test_app_with_auth.get(
            "/protected",
            headers={"X-API-Key": "test-valid-key-123"},
        )
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

    def test_invalid_api_key_via_header_returns_401(self, test_app_with_auth):
        """REQ-SEC-002: 잘못된 X-API-Key 헤더 → 401 반환"""
        response = test_app_with_auth.get(
            "/protected",
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 401

    def test_missing_api_key_returns_401(self, test_app_with_auth):
        """REQ-SEC-002: API Key 헤더 누락 → 401 반환"""
        response = test_app_with_auth.get("/protected")
        assert response.status_code == 401

    def test_empty_api_key_returns_401(self, test_app_with_auth):
        """REQ-SEC-002: 빈 X-API-Key 헤더 → 401 반환"""
        response = test_app_with_auth.get(
            "/protected",
            headers={"X-API-Key": ""},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# REQ-SEC-001: 쿼리 파라미터 인증 제거 확인 + 추가 헤더 테스트
# ---------------------------------------------------------------------------


class TestApiKeyQueryParamRemoved:
    """api_key 쿼리 파라미터 인증이 제거되었는지 확인하는 테스트"""

    def test_query_param_api_key_no_longer_accepted(self, test_app_with_auth):
        """FIX-SEC-001: 쿼리 파라미터로 API Key를 전달해도 인증 실패"""
        response = test_app_with_auth.get(
            "/protected?api_key=test-valid-key-123",
        )
        assert response.status_code == 401

    def test_second_valid_key_works_via_header(self, test_app_with_auth):
        """REQ-SEC-003: 두 번째 유효한 키도 헤더를 통해 동작해야 함"""
        response = test_app_with_auth.get(
            "/protected",
            headers={"X-API-Key": "another-valid-key"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# REQ-SEC-004: API_KEYS 미설정 시 개발 모드 (인증 비활성화)
# ---------------------------------------------------------------------------


class TestDevModeNoAuth:
    """API_KEYS 미설정 시 인증 비활성화 테스트"""

    def test_no_api_key_required_when_api_keys_not_set(self, test_app_no_auth):
        """REQ-SEC-004: API_KEYS 환경 변수 미설정 → 인증 없이 접근 허용"""
        response = test_app_no_auth.get("/protected")
        assert response.status_code == 200

    def test_any_api_key_allowed_when_auth_disabled(self, test_app_no_auth):
        """REQ-SEC-004: API_KEYS 미설정 시 임의 키도 허용"""
        response = test_app_no_auth.get(
            "/protected",
            headers={"X-API-Key": "any-key"},
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# REQ-SEC-005: API Key 평문 로그 금지
# ---------------------------------------------------------------------------


class TestApiKeyLogging:
    """API Key 로깅 보안 테스트"""

    def test_api_key_not_logged_in_plaintext(self):
        """REQ-SEC-005: verify_api_key 호출 시 API Key 평문 로그 없음"""

        from backend.app.middleware.auth import verify_api_key

        # 로그 캡처 설정
        with patch("backend.app.middleware.auth.logger") as mock_logger:
            with patch("backend.app.middleware.auth.settings") as mock_settings:
                mock_settings.api_keys = ["secret-key-12345"]

                # FastAPI Request 모의 객체 생성
                mock_request = MagicMock(spec=Request)
                mock_request.headers = {"x-api-key": "secret-key-12345"}
                mock_request.query_params = {}

                # 동기 호출 방식으로 검증
                import asyncio

                async def run_verify():
                    return await verify_api_key(
                        api_key_header="secret-key-12345",
                    )

                asyncio.run(run_verify())

                # logger에 전달된 모든 호출에서 평문 키가 없는지 확인
                for call in mock_logger.mock_calls:
                    call_str = str(call)
                    assert "secret-key-12345" not in call_str, (
                        f"API Key가 평문으로 로그에 남았습니다: {call_str}"
                    )

    def test_invalid_key_error_message_does_not_contain_key(self, test_app_with_auth):
        """REQ-SEC-005: 인증 실패 응답에 실제 키 값이 포함되지 않음"""
        response = test_app_with_auth.get(
            "/protected",
            headers={"X-API-Key": "my-secret-key"},
        )
        assert response.status_code == 401
        response_text = response.text
        assert "my-secret-key" not in response_text
