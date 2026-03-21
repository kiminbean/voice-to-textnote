"""
API Key 인증 미들웨어
REQ-SEC-001: X-API-Key 헤더 또는 api_key 쿼리 파라미터 인증
REQ-SEC-002: 누락/잘못된 API Key → 401 반환
REQ-SEC-003: 유효한 API Key → 정상 처리
REQ-SEC-004: API_KEYS 미설정 시 인증 비활성화 (개발 모드)
REQ-SEC-005: API Key 평문 로그 금지
"""


from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery

from backend.app.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# API Key 추출 스킴 정의
# auto_error=False: 키가 없어도 예외를 바로 던지지 않고 None 반환 (직접 처리)
_api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query_scheme = APIKeyQuery(name="api_key", auto_error=False)


async def verify_api_key(
    api_key_header: str | None = Security(_api_key_header_scheme),
    api_key_query: str | None = Security(_api_key_query_scheme),
) -> str:
    """
    API Key 인증 의존성 함수
    REQ-SEC-001: X-API-Key 헤더 또는 api_key 쿼리 파라미터에서 키 추출
    REQ-SEC-004: API_KEYS가 비어있으면 개발 모드 - 인증 건너뜀
    REQ-SEC-005: 키 평문은 절대 로그에 남기지 않음
    """
    # REQ-SEC-004: API_KEYS 미설정 시 개발 모드 - 모든 요청 허용
    if not settings.api_keys:
        logger.debug("인증 비활성화 (개발 모드 - API_KEYS 미설정)")
        return "dev-mode"

    # 헤더 또는 쿼리 파라미터에서 키 추출
    api_key = api_key_header or api_key_query

    # REQ-SEC-002: API Key 누락 시 401 반환
    if not api_key:
        logger.warning("API Key 누락 - 인증 거부")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key가 필요합니다. X-API-Key 헤더 또는 api_key 쿼리 파라미터를 제공하세요.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # REQ-SEC-003: 유효한 키 검증
    # REQ-SEC-005: 키의 앞 4자리만 로그에 기록 (평문 금지)
    if api_key in settings.api_keys:
        key_prefix = api_key[:4] + "****" if len(api_key) >= 4 else "****"
        logger.debug("API Key 인증 성공", key_prefix=key_prefix)
        return api_key

    # REQ-SEC-002: 잘못된 키 시 401 반환 (키 값은 로그에 포함하지 않음)
    logger.warning("잘못된 API Key - 인증 거부")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 API Key입니다.",
        headers={"WWW-Authenticate": "ApiKey"},
    )
