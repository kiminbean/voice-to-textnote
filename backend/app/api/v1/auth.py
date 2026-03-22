"""
SPEC-TEAM-001: 인증 API 엔드포인트

공개 엔드포인트 (API Key 불필요):
- POST /auth/register - 회원 가입
- POST /auth/login    - 로그인
- POST /auth/refresh  - access token 갱신
- POST /auth/logout   - 로그아웃

인증 필요 엔드포인트:
- GET /auth/me - 현재 사용자 정보 조회
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_service import AuthService
from backend.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# AuthService 인스턴스 (재사용)
_auth_service = AuthService()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원 가입",
)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    새 사용자 계정을 생성하고 JWT 토큰을 반환합니다.

    - **email**: 이메일 주소 (유니크)
    - **password**: 비밀번호 (최소 8자, 영문자+숫자 포함)
    - **display_name**: 표시 이름
    """
    _, access_token, refresh_token = await _auth_service.register(
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
) -> TokenResponse:
    """
    이메일/비밀번호로 로그인하고 JWT 토큰을 반환합니다.
    """
    _, access_token, refresh_token = await _auth_service.login(
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
) -> TokenResponse:
    """
    Refresh Token으로 새 Access Token과 Refresh Token을 발급합니다.
    기존 Refresh Token은 폐기됩니다 (rotation).
    """
    new_access, new_refresh = await _auth_service.refresh(
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
) -> None:
    """
    Refresh Token을 폐기하여 로그아웃합니다.
    """
    await _auth_service.logout(session=db, refresh_token_str=req.refresh_token)


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
    )
