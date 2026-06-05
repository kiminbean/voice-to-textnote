"""
SPEC-TEAM-001: 인증 API 엔드포인트
SPEC-GUEST-001: 게스트 세션 엔드포인트 추가
REQ-OAUTH-001: 소셜 로그인 엔드포인트 추가

공개 엔드포인트 (API Key 불필요):
- POST /auth/register - 회원 가입
- POST /auth/login    - 로그인
- POST /auth/refresh  - access token 갱신
- POST /auth/logout   - 로그아웃
- POST /auth/guest    - 게스트 세션 생성 (SPEC-GUEST-001)
- POST /auth/google   - Google 소셜 로그인 (REQ-OAUTH-001)
- POST /auth/apple    - Apple 소셜 로그인 (REQ-OAUTH-001)

인증 필요 엔드포인트:
- GET  /auth/me            - 현재 사용자 정보 조회
- POST /auth/link/{provider}   - 소셜 계정 연동
- DELETE /auth/link/{provider}  - 소셜 계정 연동 해제
"""

import json
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.dependencies import get_current_user, get_db_session, get_redis_client
from backend.app.errors import bad_request, unauthorized
from backend.schemas.auth import (
    AppleLoginRequest,
    GoogleLoginRequest,
    GuestSessionResponse,
    LinkProviderRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.services.auth_service import AuthService
from backend.services.oauth_service import (
    verify_apple_token,
    verify_google_token,
)
from backend.utils.logger import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    """AuthService 인스턴스 제공 (FastAPI Depends)"""
    return AuthService()


logger = get_logger(__name__)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원 가입",
)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    새 사용자 계정을 생성하고 JWT 토큰을 반환합니다.

    - **email**: 이메일 주소 (유니크)
    - **password**: 비밀번호 (최소 8자, 영문자+숫자 포함)
    - **display_name**: 표시 이름
    """
    _, access_token, refresh_token = await auth_service.register(
        session=db,
        email=req.email,
        password=req.password,
        display_name=req.display_name,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인",
)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    이메일/비밀번호로 로그인하고 JWT 토큰을 반환합니다.
    """
    _, access_token, refresh_token = await auth_service.login(
        session=db,
        email=req.email,
        password=req.password,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Access Token 갱신",
)
async def refresh_token(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Refresh Token으로 새 Access Token과 Refresh Token을 발급합니다.
    기존 Refresh Token은 폐기됩니다 (rotation).
    """
    new_access, new_refresh = await auth_service.refresh(
        session=db,
        refresh_token_str=req.refresh_token,
    )
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
)
async def logout(
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """
    Refresh Token을 폐기하여 로그아웃합니다.
    """
    await auth_service.logout(session=db, refresh_token_str=req.refresh_token)


@router.post(
    "/guest",
    response_model=GuestSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="게스트 세션 생성",
)
async def create_guest_session(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> GuestSessionResponse:
    """
    SPEC-GUEST-001: 게스트 세션을 생성하고 JWT를 반환합니다.

    - 로그인 없이 임시 세션을 생성합니다.
    - 24시간 유효한 JWT 토큰을 발급합니다.
    - Redis에 세션 정보를 저장합니다 (TTL 86400초).
    """
    # REQ-GUEST-001: UUID v4 게스트 세션 ID 생성
    guest_session_id = str(uuid.uuid4())

    # REQ-GUEST-004: 만료 시각 계산 (24시간 후)
    ttl_hours = settings.guest_session_ttl_hours
    expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours)

    # REQ-GUEST-002: JWT 생성 (type: "guest" 포함)
    payload = {
        "sub": guest_session_id,
        "type": "guest",
        "exp": expires_at,
    }
    guest_token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    # REQ-GUEST-003: Redis에 세션 저장 (TTL: 86400초 = 24시간)
    redis_key = f"guest:session:{guest_session_id}"
    session_data = json.dumps({"created_at": datetime.now(UTC).isoformat()})
    await redis.setex(redis_key, ttl_hours * 3600, session_data)

    return GuestSessionResponse(
        guest_session_id=guest_session_id,
        guest_token=guest_token,
        expires_at=expires_at,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="현재 사용자 정보",
)
async def get_me(
    current_user=Depends(get_current_user),
) -> UserResponse:
    """
    Bearer JWT 토큰으로 현재 사용자 정보를 반환합니다.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        provider=current_user.provider,
        avatar_url=current_user.avatar_url,
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Google 소셜 로그인",
)
async def google_login(
    req: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """REQ-OAUTH-001: Google ID token으로 로그인/자동가입."""
    try:
        user_info = await verify_google_token(req.id_token)
    except ValueError as e:
        unauthorized(str(e))

    _, access_token, refresh_token = await auth_service.social_login_or_register(
        session=db,
        provider=user_info.provider,
        provider_id=user_info.provider_id,
        email=user_info.email,
        display_name=user_info.display_name,
        avatar_url=user_info.avatar_url,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/apple",
    response_model=TokenResponse,
    summary="Apple 소셜 로그인",
)
async def apple_login(
    req: AppleLoginRequest,
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """REQ-OAUTH-001: Apple ID token으로 로그인/자동가입."""
    try:
        user_info = await verify_apple_token(req.id_token)
    except ValueError as e:
        unauthorized(str(e))

    display_name = req.display_name or user_info.display_name

    _, access_token, refresh_token = await auth_service.social_login_or_register(
        session=db,
        provider=user_info.provider,
        provider_id=user_info.provider_id,
        email=user_info.email,
        display_name=display_name,
        avatar_url=user_info.avatar_url,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/link/{provider}",
    response_model=UserResponse,
    summary="소셜 계정 연동",
)
async def link_provider(
    provider: str,
    req: LinkProviderRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """REQ-OAUTH-001: 기존 계정에 소셜 제공자 연동."""
    if provider not in ("google", "apple"):
        bad_request("지원하지 않는 제공자입니다")

    verify_fn = verify_google_token if provider == "google" else verify_apple_token
    try:
        user_info = await verify_fn(req.id_token)
    except ValueError as e:
        unauthorized(str(e))

    updated_user = await auth_service.link_provider(
        session=db,
        user=current_user,
        provider=provider,
        provider_id=user_info.provider_id,
        avatar_url=user_info.avatar_url,
    )
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        display_name=updated_user.display_name,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
        provider=updated_user.provider,
        avatar_url=updated_user.avatar_url,
    )


@router.delete(
    "/link/{provider}",
    response_model=UserResponse,
    summary="소셜 계정 연동 해제",
)
async def unlink_provider(
    provider: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """REQ-OAUTH-001: 소셜 제공자 연동 해제."""
    if provider not in ("google", "apple"):
        bad_request("지원하지 않는 제공자입니다")

    updated_user = await auth_service.unlink_provider(
        session=db,
        user=current_user,
        provider=provider,
    )
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        display_name=updated_user.display_name,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
        provider=updated_user.provider,
        avatar_url=updated_user.avatar_url,
    )
