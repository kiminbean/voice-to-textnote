"""
Request ID 미들웨어
REQ-OPS-005: 모든 HTTP 요청에 UUID Request ID 부여, X-Request-ID 응답 헤더 포함
REQ-OPS-006: 모든 로그 항목에 Request ID 포함 (structlog contextvars 사용)
REQ-OPS-007: 클라이언트가 X-Request-ID 헤더 제공 시 해당 ID 사용
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    모든 HTTP 요청에 고유 Request ID를 부여하는 미들웨어

    REQ-OPS-005: UUID 기반 Request ID 자동 부여
    REQ-OPS-006: structlog context에 request_id 바인딩 (모든 로그에 포함)
    REQ-OPS-007: 클라이언트 제공 X-Request-ID 헤더 우선 사용
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청마다 Request ID 할당 및 컨텍스트 바인딩"""
        # REQ-OPS-007: 클라이언트 제공 X-Request-ID 우선 사용, 없으면 UUID 생성
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # REQ-OPS-006: structlog context에 request_id 바인딩 (이후 모든 로그에 자동 포함)
        clear_contextvars()
        bind_contextvars(request_id=request_id)

        # 요청 처리
        response = await call_next(request)

        # REQ-OPS-005: 응답 헤더에 X-Request-ID 추가
        response.headers["X-Request-ID"] = request_id

        return response
