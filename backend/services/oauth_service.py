"""
REQ-OAUTH-001: Google/Apple OAuth 토큰 검증 서비스

클라이언트에서 받은 ID token을 검증하고 사용자 정보를 추출합니다.
토큰은 검증용으로만 사용하고 저장하지 않습니다 (privacy-first).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from backend.app.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


@dataclass(frozen=True)
class OAuthUserInfo:
    """OAuth 검증 결과 사용자 정보"""

    provider: str  # "google" | "apple"
    provider_id: str  # Google sub or Apple user ID
    email: str
    display_name: str
    avatar_url: str | None = None


async def verify_google_token(id_token: str) -> OAuthUserInfo:
    """
    Google ID token을 검증하고 사용자 정보를 반환합니다.

    검증 단계:
    1. Google 공개 키로 JWT 서명 검증
    2. aud(client_id) 일치 확인
    3. iss(issuer) 일치 확인
    4. exp(만료) 확인
    """
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID가 설정되지 않았습니다")

    # Google 공개 키 가져오기
    async with httpx.AsyncClient() as client:
        resp = await client.get(_GOOGLE_CERTS_URL)
        resp.raise_for_status()
        certs = resp.json()

    # JWT 헤더에서 kid 추출 후 공개 키 선택
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Google ID token에 kid가 없습니다")

    public_key = None
    for key in certs.get("keys", []):
        if key.get("kid") == kid:
            public_key = key
            break

    if public_key is None:
        raise ValueError("Google 공개 키를 찾을 수 없습니다")

    # JWT 검증 (서명, 만료, issuer, audience)
    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=_GOOGLE_ISSUERS,
        )
    except JWTError as e:
        raise ValueError(f"Google ID token 검증 실패: {e}") from e

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise ValueError("Google ID token에 필수 필드(sub, email)가 없습니다")

    return OAuthUserInfo(
        provider="google",
        provider_id=sub,
        email=email,
        display_name=payload.get("name", email.split("@")[0]),
        avatar_url=payload.get("picture"),
    )


async def verify_apple_token(id_token: str) -> OAuthUserInfo:
    """
    Apple ID token을 검증하고 사용자 정보를 반환합니다.

    검증 단계:
    1. Apple 공개 키로 JWT 서명 검증
    2. aud(client_id/team_id) 일치 확인
    3. iss(issuer) "https://appleid.apple.com" 확인
    4. exp(만료) 확인
    """
    if not settings.apple_client_id or not settings.apple_team_id:
        raise ValueError("Apple Sign-In 설정(APPLE_CLIENT_ID, APPLE_TEAM_ID)이 필요합니다")

    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise ValueError("Apple ID token에 kid가 없습니다")

    apple_certs_url = "https://appleid.apple.com/auth/keys"

    async with httpx.AsyncClient() as client:
        resp = await client.get(apple_certs_url)
        resp.raise_for_status()
        certs = resp.json()

    public_key = None
    for key in certs.get("keys", []):
        if key.get("kid") == kid:
            public_key = key
            break

    if public_key is None:
        raise ValueError("Apple 공개 키를 찾을 수 없습니다")

    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer="https://appleid.apple.com",
        )
    except JWTError as e:
        raise ValueError(f"Apple ID token 검증 실패: {e}") from e

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub:
        raise ValueError("Apple ID token에 필수 필드(sub)가 없습니다")

    # Apple은 최초 로그인 시에만 email을 제공하고, 이후에는 숨겨질 수 있음
    display_name = email.split("@")[0] if email else f"apple_{sub[:8]}"

    return OAuthUserInfo(
        provider="apple",
        provider_id=sub,
        email=email or f"{sub}@apple.privaterelay",
        display_name=display_name,
        avatar_url=None,
    )


def verify_apple_code_callback(code: str) -> dict:
    """
    Apple authorization code를 검증합니다 (초기 구현에서는 미사용).
    추후 Apple private email relay 기능이 필요할 때 활성화.
    """
    logger.warning("Apple authorization code callback은 아직 구현되지 않았습니다")
    return {}
