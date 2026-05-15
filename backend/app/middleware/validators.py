"""
경로 파라미터 유효성 검증 미들웨어
FIX-SEC-004: task_id 등 경로 파라미터의 경로 탐색(Path Traversal) 공격 방지
"""

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 안전한 경로 세그먼트 패턴: 영숫자, 하이픈, 언더스코어만 허용 (최대 128자)
_SAFE_SEGMENT_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# 검증 대상 경로 접두사 (API 엔드포인트만 검증)
_API_PREFIX = "/api/v1/"

# 검증 제외 경로 세그먼트 (라우터 접두사 등 고정 값)
_KNOWN_SEGMENTS = frozenset({
    "api", "v1", "transcriptions", "diarizations", "minutes",
    "summaries", "tasks", "history", "health", "metrics",
    "status", "stream", "admin", "retention", "keywords", "extract", "recommend",
})


class PathValidationMiddleware(BaseHTTPMiddleware):
    """
    API 경로 세그먼트의 안전성을 검증하는 미들웨어
    경로 탐색 공격(.., /, \\) 및 비정상 문자 차단
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # API 엔드포인트만 검증
        if not path.startswith(_API_PREFIX):
            return await call_next(request)

        # 경로 세그먼트 분리 후 동적 파라미터(task_id 등) 검증
        segments = [s for s in path.split("/") if s]
        for segment in segments:
            # 알려진 고정 세그먼트는 건너뜀
            if segment in _KNOWN_SEGMENTS:
                continue

            # 경로 탐색 패턴 차단
            if ".." in segment or "/" in segment or "\\" in segment:
                logger.warning("경로 탐색 시도 차단", path=path)
                return JSONResponse(
                    status_code=400,
                    content={"detail": "유효하지 않은 경로 파라미터입니다"},
                )

            # 길이 및 문자 패턴 검증
            if len(segment) > 128 or not _SAFE_SEGMENT_PATTERN.match(segment):
                logger.warning("비정상 경로 세그먼트 차단", path=path, segment=segment[:20])
                return JSONResponse(
                    status_code=400,
                    content={"detail": "유효하지 않은 경로 파라미터입니다"},
                )

        return await call_next(request)
