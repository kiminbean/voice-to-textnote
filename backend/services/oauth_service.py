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


def _google_audiences() -> list[str]:
    """Return comma-separated Google OAuth client IDs accepted by the backend."""
    raw_audiences = settings.google_client_id or ""
    return [
        audience.strip()
        for audience in raw_audiences.split(",")
        if audience.strip()
    ]


def _audience_matches(token_audience: str | list[str] | tuple[str, ...] | None, audiences: list[str]) -> bool:
    if token_audience is None:
        return False
    if isinstance(token_audience, str):
        token_audiences = {token_audience}
    else:
        token_audiences = {audience for audience in token_audience if isinstance(audience, str)}
    return bool(token_audiences.intersection(audiences))


async def verify_google_token(id_token: str) -> OAuthUserInfo:
    """
    Google ID token을 검증하고 사용자 정보를 반환합니다.

    검증 단계:
    1. Google 공개 키로 JWT 서명 검증
    2. aud(client_id) 일치 확인
    3. iss(issuer) 일치 확인
    4. exp(만료) 확인
    """
    audiences = _google_audiences()
    if not audiences:
        raise ValueError("GOOGLE_CLIENT_ID가 설정되지 않았습니다")

    # Google 공개 키 가져오기
    async with httpx.AsyncClient() as client:
        resp = await client.get(_GOOGLE_CERTS_URL)
        resp.raise_for_status()
        certs = resp.json()

    # JWT 헤더에서 kid 추출 후 공개 키 선택
    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise ValueError(f"Google ID token 헤더 검증 실패: {e}") from e
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

    try:
        unverified_claims = jwt.get_unverified_claims(id_token)
    except JWTError:
        unverified_claims = {}

    # JWT 검증 (서명, 만료) 후 issuer/audience는 명시적으로 검사한다.
    # python-jose의 audience/issuer 검증은 다중 네이티브 OAuth client ID를
    # 허용하는 모바일 앱 구성에서 실패 원인 추적이 어렵기 때문에 분리한다.
    try:
        payload = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_at_hash": False},
        )
    except JWTError as e:
        raise ValueError(f"Google ID token 검증 실패: {e}") from e

    issuer = payload.get("iss")
    if issuer not in _GOOGLE_ISSUERS:
        raise ValueError(f"Google ID token issuer 불일치: {issuer}")

    token_audience = payload.get("aud")
    if not _audience_matches(token_audience, audiences):
        logger.warning(
            "Google ID token audience mismatch",
            token_audience=token_audience or unverified_claims.get("aud"),
            authorized_audience_count=len(audiences),
            authorized_audience_suffixes=[audience.split(".")[0][-12:] for audience in audiences],
            azp=payload.get("azp") or unverified_claims.get("azp"),
        )
        raise ValueError("Google ID token audience가 서버 설정과 일치하지 않습니다")

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

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise ValueError(f"Apple ID token 헤더 검증 실패: {e}") from e
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
    Apple authorization code 콜백은 현재 서버 인증 플로우에서 지원하지 않는다.

    모바일 클라이언트는 /auth/apple 엔드포인트로 ID token을 전달하고,
    서버는 verify_apple_token()에서 해당 토큰을 검증한다. Authorization
    code 교환은 Apple private key 기반 client_secret 설정이 추가될 때
    별도 구현해야 하므로, 빈 dict를 반환하지 않고 명시적으로 실패시킨다.
    """
    if not code.strip():
        raise ValueError("Apple authorization code가 비어 있습니다")

    logger.warning("Apple authorization code callback은 현재 지원하지 않습니다")
    raise ValueError("Apple authorization code callback은 현재 지원하지 않습니다")
