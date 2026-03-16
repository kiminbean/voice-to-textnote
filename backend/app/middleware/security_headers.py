"""
보안 헤더 미들웨어
REQ-SEC-011: 모든 응답에 X-Content-Type-Options, X-Frame-Options, X-XSS-Protection 헤더 추가
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    모든 HTTP 응답에 보안 헤더를 추가하는 미들웨어
    REQ-SEC-011: OWASP 권장 보안 헤더 적용
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청 처리 후 응답에 보안 헤더 추가"""
        response = await call_next(request)

        # REQ-SEC-011: MIME 타입 스니핑 방지
        response.headers["X-Content-Type-Options"] = "nosniff"

        # REQ-SEC-011: 클릭재킹 방지
        response.headers["X-Frame-Options"] = "DENY"

        # REQ-SEC-011: XSS 필터 활성화
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response
