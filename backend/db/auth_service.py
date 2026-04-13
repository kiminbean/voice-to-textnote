"""
SPEC-TEAM-001: 인증 서비스

REQ-AUTH-001: 회원 가입 (이메일 중복 검사, bcrypt 해싱)
REQ-AUTH-002: 로그인 (자격증명 검증, JWT 발급)
REQ-AUTH-003: Refresh Token Rotation (기존 폐기, 신규 발급)
REQ-AUTH-004: 로그아웃 (refresh token 폐기)
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.auth_models import RefreshToken, User

# bcrypt 컨텍스트 (단방향 해싱)
# @MX:NOTE: deprecated=auto 설정으로 구버전 해시 자동 업그레이드
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    JWT 기반 인증 서비스.
    Access Token(15분) + Refresh Token(7일) 전략 사용.
    """

    # JWT 설정
    # @MX:ANCHOR: ACCESS_TOKEN_EXPIRE_MINUTES 변경 시 클라이언트 세션 정책도 함께 변경 필요
    # @MX:REASON: 모바일 앱 자동 로그아웃 주기와 연동됨
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 7

    @property
    def _secret_key(self) -> str:
        """설정에서 JWT 시크릿 키 조회"""
        return settings.jwt_secret

    def hash_password(self, password: str) -> str:
        """비밀번호를 bcrypt로 해싱"""
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        """평문 비밀번호와 해시 비교"""
        return pwd_context.verify(plain, hashed)

    def create_access_token(
        self,
        user_id: str,
        email: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        JWT access token 생성.

        payload 구성:
        - sub: user_id (표준 claim)
        - email: 사용자 이메일
        - exp: 만료 시각
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        now = datetime.now(UTC)
        expire = now + expires_delta
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self.ALGORITHM)

    def create_refresh_token(self) -> str:
        """
        Refresh token 원본 문자열 생성 (cryptographically random).
        DB에는 SHA-256 해시만 저장.
        """
        return secrets.token_urlsafe(32)

    def decode_access_token(self, token: str) -> dict:
        """
        JWT access token 디코딩 및 검증.
        만료/서명 오류 시 401 HTTPException 발생.
        """
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self.ALGORITHM])
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="유효하지 않거나 만료된 토큰입니다",
            )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="유효하지 않은 토큰입니다",
            )

        return payload

    @staticmethod
    def _hash_token(token: str) -> str:
        """refresh token SHA-256 해싱 (DB 저장용)"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def register(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str,
    ) -> tuple[User, str, str]:
        """
        회원 가입.

        Returns:
            (User, access_token, refresh_token) 튜플

        Raises:
            HTTPException(409): 이메일 중복
        """
        # 이메일 중복 검사
        existing = await session.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")

        # 사용자 생성
        user = User()
        user.id = uuid.uuid4()
        user.email = email
        user.password_hash = self.hash_password(password)
        user.display_name = display_name
        user.is_active = True
        session.add(user)

        # refresh token 생성 및 저장
        raw_refresh = self.create_refresh_token()
        refresh_record = RefreshToken()
        refresh_record.id = uuid.uuid4()
        refresh_record.user_id = user.id
        refresh_record.token_hash = self._hash_token(raw_refresh)
        refresh_record.expires_at = (
            datetime.now(UTC) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        ).replace(tzinfo=None)
        refresh_record.is_revoked = False
        session.add(refresh_record)

        await session.commit()

        access_token = self.create_access_token(str(user.id), user.email)
        return user, access_token, raw_refresh

    async def login(
        self,
        session: AsyncSession,
        email: str,
        password: str,
    ) -> tuple[User, str, str]:
        """
        로그인.

        Returns:
            (User, access_token, refresh_token) 튜플

        Raises:
            HTTPException(401): 이메일 없음 또는 비밀번호 불일치
        """
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # 이메일/비밀번호 모두 같은 에러 반환 (사용자 열거 방지)
        if user is None or not self.verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="이메일 또는 비밀번호가 올바르지 않습니다",
            )

        if not user.is_active:
            raise HTTPException(status_code=401, detail="비활성화된 계정입니다")

        # refresh token 생성
        raw_refresh = self.create_refresh_token()
        refresh_record = RefreshToken()
        refresh_record.id = uuid.uuid4()
        refresh_record.user_id = user.id
        refresh_record.token_hash = self._hash_token(raw_refresh)
        refresh_record.expires_at = (
            datetime.now(UTC) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        ).replace(tzinfo=None)
        refresh_record.is_revoked = False
        session.add(refresh_record)
        await session.commit()

        access_token = self.create_access_token(str(user.id), user.email)
        return user, access_token, raw_refresh

    async def refresh(
        self,
        session: AsyncSession,
        refresh_token_str: str,
    ) -> tuple[str, str]:
        """
        Refresh Token Rotation.
        기존 토큰을 폐기하고 새 토큰 쌍을 발급합니다.

        Returns:
            (new_access_token, new_refresh_token) 튜플

        Raises:
            HTTPException(401): 토큰 없음, 만료, 또는 폐기됨
        """
        token_hash = self._hash_token(refresh_token_str)

        # refresh token 조회
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_record = result.scalar_one_or_none()

        if token_record is None:
            raise HTTPException(status_code=401, detail="유효하지 않은 refresh token입니다")

        # 만료 또는 폐기 확인
        now = datetime.now(UTC).replace(tzinfo=None)
        if token_record.is_revoked or token_record.expires_at < now:
            raise HTTPException(status_code=401, detail="만료되었거나 폐기된 refresh token입니다")

        # 기존 토큰 폐기 (rotation)
        token_record.is_revoked = True

        # 사용자 조회
        user_result = await session.execute(
            select(User).where(User.id == token_record.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

        # 새 refresh token 생성
        new_raw_refresh = self.create_refresh_token()
        new_record = RefreshToken()
        new_record.id = uuid.uuid4()
        new_record.user_id = user.id
        new_record.token_hash = self._hash_token(new_raw_refresh)
        new_record.expires_at = (
            datetime.now(UTC) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        ).replace(tzinfo=None)
        new_record.is_revoked = False
        session.add(new_record)

        await session.commit()

        new_access = self.create_access_token(str(user.id), user.email)
        return new_access, new_raw_refresh

    async def logout(
        self,
        session: AsyncSession,
        refresh_token_str: str,
    ) -> None:
        """
        로그아웃 - refresh token 폐기.
        토큰이 없어도 에러 없이 처리 (멱등성).
        """
        token_hash = self._hash_token(refresh_token_str)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_record = result.scalar_one_or_none()

        if token_record is not None:
            token_record.is_revoked = True
            await session.commit()
