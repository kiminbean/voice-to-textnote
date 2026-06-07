"""
API Key 인증 미들웨어
REQ-SEC-001: X-API-Key 헤더 전용 인증 (쿼리 파라미터 노출 방지)
REQ-SEC-002: 누락/잘못된 API Key → 401 반환
REQ-SEC-003: 유효한 API Key → 정상 처리
REQ-SEC-004: API_KEYS 미설정 시 인증 비활성화 (개발 모드)
REQ-SEC-005: API Key 평문 로그 금지
REQ-GUEST-005: Bearer guest:<token> 형식 게스트 토큰 인증 지원
SPEC-TEAM-001: Bearer <jwt> 액세스 토큰 인증 지원
"""

import secrets

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt

from backend.app.config import settings
from backend.app.dependencies import get_redis_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# API Key 추출 스킴 정의 (헤더 전용 - URL/로그 노출 방지)
# auto_error=False: 키가 없어도 예외를 바로 던지지 않고 None 반환 (직접 처리)
_api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_guest_token(
    request: Request,
    token_str: str,
    redis_client: aioredis.Redis,
) -> str:
    """
    REQ-GUEST-005: 게스트 JWT 토큰 검증

    1. JWT 디코딩 및 서명 검증
    2. type 클레임 = "guest" 확인
    3. Redis에서 세션 존재 여부 확인

    Returns:
        검증된 guest_session_id

    Raises:
        HTTPException(401): 토큰 무효 또는 세션 만료
    """
    try:
        payload = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        logger.warning("게스트 토큰 JWT 디코딩 실패")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 게스트 토큰입니다.",
        )

    # type 클레임 검증
    if payload.get("type") != "guest":
        logger.warning("게스트 토큰 type 클레임 불일치")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 게스트 토큰입니다.",
        )

    guest_session_id = payload.get("sub")
    if not guest_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 게스트 토큰입니다.",
        )

    # Redis에서 세션 존재 여부 확인
    redis_key = f"guest:session:{guest_session_id}"
    exists = await redis_client.exists(redis_key)
    if not exists:
        logger.warning("게스트 세션 만료 또는 미존재")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="게스트 세션이 만료되었거나 존재하지 않습니다.",
        )

    # request.state에 게스트 정보 설정
    request.state.is_guest = True
    request.state.guest_session_id = guest_session_id

    return guest_session_id


async def _verify_access_token(
    request: Request,
    token_str: str,
    redis_client: aioredis.Redis,
) -> str:
    """
    SPEC-TEAM-001: JWT 액세스 토큰 검증

    1. JWT 디코딩 및 서명 검증
    2. type 클레임 = "access" 확인
    3. request.state에 사용자 정보 설정

    Returns:
        검증된 user_id
    """
    try:
        payload = jwt.decode(token_str, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다.",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    request.state.is_guest = False
    request.state.user_id = user_id
    request.state.user_email = payload.get("email", "")

    return user_id


# @MX:ANCHOR: API Key + 게스트 토큰 통합 인증 의존성
# @MX:REASON: fan_in >= 3 (main.py, 각 API 라우터에서 Depends로 사용)
async def verify_api_key(
    request: Request = None,  # type: ignore[assignment]
    api_key_header: str | None = Security(_api_key_header_scheme),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> str:
    """
    API Key 인증 의존성 함수 (게스트 토큰 지원 추가)

    인증 우선순위:
    1. Authorization: Bearer guest:<token> → 게스트 토큰 검증 (REQ-GUEST-005)
    2. X-API-Key 헤더 → 기존 API Key 검증 (REQ-SEC-001~005)

    REQ-SEC-001: X-API-Key 헤더에서만 키 추출 (쿼리 파라미터는 URL/로그 노출 위험)
    REQ-SEC-004: API_KEYS가 비어있으면 개발 모드 - 인증 건너뜀
    REQ-SEC-005: 키 평문은 절대 로그에 남기지 않음
    """
    # Bearer 토큰 인증 처리 (게스트 + JWT 액세스 토큰)
    if request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token_str = auth_header[len("Bearer ") :]
            # 게스트 토큰: "guest:" 접두사
            if token_str.startswith("guest:"):
                return await _verify_guest_token(request, token_str[len("guest:") :], redis_client)
            # JWT 액세스 토큰 (SPEC-TEAM-001)
            return await _verify_access_token(request, token_str, redis_client)

    # REQ-SEC-004: API_KEYS 미설정 시 개발 모드 - 모든 요청 허용
    if not settings.api_keys:
        if getattr(settings, "environment", "development") == "production":
            logger.error("프로덕션 환경에서 API Key 미설정")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="서버 인증 설정이 완료되지 않았습니다.",
            )
        logger.debug("인증 비활성화 (개발 모드 - API_KEYS 미설정)")
        return "dev-mode"

    # REQ-SEC-002: API Key 누락 시 401 반환
    if not api_key_header:
        logger.warning("API Key 누락 - 인증 거부")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key가 필요합니다. X-API-Key 헤더를 제공하세요.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # REQ-SEC-003: 유효한 키 검증
    # REQ-SEC-005: 키의 앞 4자리만 로그에 기록 (평문 금지)
    for configured_key in settings.api_keys:
        if secrets.compare_digest(api_key_header, configured_key):
            key_prefix = api_key_header[:4] + "****" if len(api_key_header) >= 4 else "****"
            logger.debug("API Key 인증 성공", key_prefix=key_prefix)
            return api_key_header

    # REQ-SEC-002: 잘못된 키 시 401 반환 (키 값은 로그에 포함하지 않음)
    logger.warning("잘못된 API Key - 인증 거부")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 API Key입니다.",
        headers={"WWW-Authenticate": "ApiKey"},
    )
