"""
SPEC-TEAM-001: 인증 API Pydantic 스키마
SPEC-GUEST-001: 게스트 세션 스키마 추가

REQ-AUTH-001: RegisterRequest - 이메일/비밀번호/표시명 유효성 검사
REQ-AUTH-002: LoginRequest, TokenResponse
REQ-AUTH-003: RefreshRequest
REQ-GUEST-001: GuestSessionResponse - 게스트 세션 응답 스키마
"""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """회원 가입 요청 스키마"""

    email: EmailStr
    password: str = Field(min_length=8, description="비밀번호 (최소 8자, 영문자+숫자 포함)")
    display_name: str = Field(min_length=1, max_length=100, description="표시 이름")

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        비밀번호 복잡도 검사:
        - 최소 8자 (Field min_length로 처리)
        - 영문자 최소 1개
        - 숫자 최소 1개
        """
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("비밀번호에 영문자가 최소 1개 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 최소 1개 포함되어야 합니다")
        return v


class LoginRequest(BaseModel):
    """로그인 요청 스키마"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT 토큰 응답 스키마"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh Token 갱신 요청 스키마"""

    refresh_token: str


class UserResponse(BaseModel):
    """사용자 정보 응답 스키마"""

    id: str
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    provider: str = "email"
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class GoogleLoginRequest(BaseModel):
    """REQ-OAUTH-001: Google 소셜 로그인 요청"""

    id_token: str


class AppleLoginRequest(BaseModel):
    """REQ-OAUTH-001: Apple 소셜 로그인 요청"""

    id_token: str
    display_name: str | None = None


class LinkProviderRequest(BaseModel):
    """REQ-OAUTH-001: 소셜 계정 연동 요청"""

    id_token: str


class GuestSessionResponse(BaseModel):
    """
    REQ-GUEST-001: 게스트 세션 응답 스키마

    게스트 세션 생성 시 반환되는 데이터:
    - guest_session_id: UUID v4 세션 식별자
    - guest_token: 24시간 유효한 JWT (type: "guest")
    - expires_at: 세션 만료 시각 (UTC)
    """

    guest_session_id: str
    guest_token: str
    expires_at: datetime


class ClaimGuestRequest(BaseModel):
    """게스트 회의 인계 요청 스키마.

    로그인 직후, 게스트 토큰 소지를 증명해 게스트로 녹음한 회의를 계정으로
    인계한다. guest_token은 게스트 세션 생성 시 발급된 JWT 그대로 전달한다.
    """

    guest_token: str


class ClaimGuestResponse(BaseModel):
    """게스트 회의 인계 결과 스키마."""

    claimed: int
