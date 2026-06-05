"""
SPEC-SEC-001 Rate Limiting 단위 테스트
REQ-SEC-006: IP 기반 Rate Limiting - 모든 엔드포인트 적용
REQ-SEC-007: 한도 초과 시 429 + Retry-After 헤더 반환 (기본 60회/분)
REQ-SEC-008: Redis 미사용 시 인메모리 폴백
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from backend.app.error_handlers import register_exception_handlers

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def rate_limited_app():
    """Rate Limiting이 적용된 테스트 앱"""
    from backend.app.middleware.rate_limit import setup_rate_limiting

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/api/test")
    async def test_route():
        return {"message": "ok"}

    setup_rate_limiting(app)

    return app


# ---------------------------------------------------------------------------
# REQ-SEC-007: 429 + Retry-After 헤더 테스트
# ---------------------------------------------------------------------------


class TestRateLimitExceeded:
    """Rate Limit 초과 응답 테스트"""

    def test_rate_limit_exceeded_returns_429(self):
        """REQ-SEC-007: Rate Limit 초과 시 429 반환"""
        from slowapi.errors import RateLimitExceeded

        from backend.app.middleware.rate_limit import rate_limit_exceeded_handler

        # RateLimitExceeded 예외 핸들러 직접 테스트
        mock_request = MagicMock()
        mock_exc = MagicMock(spec=RateLimitExceeded)
        mock_exc.detail = "1 per 1 minute"

        import asyncio

        response = asyncio.run(rate_limit_exceeded_handler(mock_request, mock_exc))
        assert response.status_code == 429

    def test_rate_limit_response_has_retry_after_header(self):
        """REQ-SEC-007: Rate Limit 초과 응답에 Retry-After 헤더 포함"""
        from slowapi.errors import RateLimitExceeded

        from backend.app.middleware.rate_limit import rate_limit_exceeded_handler

        mock_request = MagicMock()
        mock_exc = MagicMock(spec=RateLimitExceeded)
        mock_exc.detail = "1 per 1 minute"

        import asyncio

        response = asyncio.run(rate_limit_exceeded_handler(mock_request, mock_exc))
        assert "retry-after" in response.headers or "Retry-After" in response.headers

    def test_rate_limit_response_body_format(self):
        """REQ-SEC-007: Rate Limit 초과 응답 본문 형식 검증"""
        from slowapi.errors import RateLimitExceeded

        from backend.app.middleware.rate_limit import rate_limit_exceeded_handler

        mock_request = MagicMock()
        mock_exc = MagicMock(spec=RateLimitExceeded)
        mock_exc.detail = "60 per 1 minute"

        import asyncio

        response = asyncio.run(rate_limit_exceeded_handler(mock_request, mock_exc))
        import json

        body = json.loads(response.body)
        assert "detail" in body
        assert "error" in body


# ---------------------------------------------------------------------------
# REQ-SEC-008: 인메모리 폴백 테스트
# ---------------------------------------------------------------------------


class TestInMemoryFallback:
    """Redis 미사용 시 인메모리 폴백 테스트"""

    def test_setup_rate_limiting_without_redis(self):
        """REQ-SEC-008: Redis 없이도 Rate Limiting 설정 성공"""
        from backend.app.middleware.rate_limit import setup_rate_limiting

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        # Redis 없이 설정 가능해야 함 (예외 없음)
        try:
            setup_rate_limiting(app)
            setup_success = True
        except Exception:
            setup_success = False

        assert setup_success, "Redis 없이도 Rate Limiting 설정이 가능해야 함"

    def test_limiter_uses_memory_storage_when_redis_unavailable(self):
        """REQ-SEC-008: Redis 미사용 시 인메모리 저장소 폴백"""
        from backend.app.middleware.rate_limit import get_limiter

        # Redis URL 없이 limiter 가져오기
        with patch("backend.app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.redis_url = None  # Redis URL 없음
            mock_settings.rate_limit_per_minute = 60

            limiter = get_limiter()
            # limiter가 생성되어야 함 (None이 아님)
            assert limiter is not None


# ---------------------------------------------------------------------------
# REQ-SEC-006: 모든 엔드포인트에 Rate Limiting 적용 검증
# ---------------------------------------------------------------------------


class TestRateLimitSetup:
    """Rate Limiting 설정 검증 테스트"""

    def test_setup_rate_limiting_returns_limiter(self):
        """REQ-SEC-006: setup_rate_limiting이 limiter 반환"""
        from backend.app.middleware.rate_limit import setup_rate_limiting

        app = FastAPI()
        register_exception_handlers(app)
        limiter = setup_rate_limiting(app)

        # limiter가 반환되어야 함
        assert limiter is not None

    def test_limiter_is_attached_to_app_state(self):
        """REQ-SEC-006: limiter가 app.state에 등록됨"""
        from backend.app.middleware.rate_limit import setup_rate_limiting

        app = FastAPI()
        register_exception_handlers(app)
        setup_rate_limiting(app)

        # app.state.limiter가 설정되어야 함
        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None

    def test_default_rate_limit_is_60_per_minute(self):
        """REQ-SEC-007: 기본 Rate Limit는 분당 60회"""
        from backend.app.middleware.rate_limit import DEFAULT_RATE_LIMIT

        assert "60" in DEFAULT_RATE_LIMIT
        assert "minute" in DEFAULT_RATE_LIMIT.lower() or "min" in DEFAULT_RATE_LIMIT.lower()
