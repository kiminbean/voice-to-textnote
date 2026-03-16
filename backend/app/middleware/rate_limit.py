"""
Rate Limiting 미들웨어
REQ-SEC-006: IP 기반 Rate Limiting - 모든 엔드포인트 적용
REQ-SEC-007: 한도 초과 시 429 + Retry-After 헤더 반환 (기본 60회/분)
REQ-SEC-008: Redis 미사용 시 인메모리 폴백
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.app.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# REQ-SEC-007: 기본 Rate Limit (분당 60회)
DEFAULT_RATE_LIMIT = "60/minute"


def get_limiter() -> Limiter:
    """
    현재 설정 기반의 새 Limiter 인스턴스 반환
    REQ-SEC-008: 인메모리 저장소 사용 (Redis 연결 오류 방지)
    분산 환경 Rate Limit이 필요한 경우 Redis storage_uri 설정 가능
    """
    return _create_limiter()


def _create_limiter() -> Limiter:
    """설정 기반 인메모리 Limiter 생성 (내부용)"""
    rate_limit = getattr(settings, "rate_limit_per_minute", 60)
    return Limiter(
        key_func=get_remote_address,
        default_limits=[f"{rate_limit}/minute"],
    )


def setup_rate_limiting(app: FastAPI) -> Limiter:
    """
    FastAPI 앱에 Rate Limiting 미들웨어 설정
    REQ-SEC-006: 모든 엔드포인트에 IP 기반 Rate Limiting 적용
    REQ-SEC-007: 429 + Retry-After 헤더 응답 핸들러 등록
    매번 새 Limiter를 생성하여 앱별 격리 보장 (테스트 안정성)
    """
    limiter = _create_limiter()

    # app.state에 limiter 등록 (slowapi 요구사항)
    app.state.limiter = limiter

    # REQ-SEC-007: RateLimitExceeded 예외 핸들러 등록
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # SlowAPI 미들웨어 추가
    app.add_middleware(SlowAPIMiddleware)

    logger.info("Rate Limiting 미들웨어 설정 완료", default_limit=DEFAULT_RATE_LIMIT)
    return limiter


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Rate Limit 초과 시 429 응답 반환
    REQ-SEC-007: 429 상태코드와 Retry-After 헤더 포함
    """
    # Retry-After 기본값: 60초 (분당 제한)
    retry_after = 60

    logger.warning(
        "Rate Limit 초과",
        client_ip=get_remote_address(request),
        detail=str(exc.detail) if hasattr(exc, "detail") else "rate limit exceeded",
    )

    return JSONResponse(
        status_code=429,
        content={
            "detail": "요청 한도를 초과했습니다. 잠시 후 다시 시도하세요.",
            "error": "rate_limit_exceeded",
        },
        headers={"Retry-After": str(retry_after)},
    )
