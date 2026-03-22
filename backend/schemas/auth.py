"""
SPEC-TEAM-001: 인증 API Pydantic 스키마

REQ-AUTH-001: RegisterRequest - 이메일/비밀번호/표시명 유효성 검사
REQ-AUTH-002: LoginRequest, TokenResponse
REQ-AUTH-003: RefreshRequest
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

    model_config = {"from_attributes": True}
