"""
SPEC-TEAM-001: AuthService 단위 테스트 (TDD RED Phase)

REQ-AUTH-001: 회원 가입 - 이메일/비밀번호/표시명
REQ-AUTH-002: 로그인 - JWT 발급
REQ-AUTH-003: JWT 갱신 - refresh token rotation
REQ-AUTH-004: 로그아웃 - refresh token 폐기
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import RefreshToken, User

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_service():
    """AuthService 인스턴스"""
    from backend.db.auth_service import AuthService
    return AuthService()


@pytest.fixture
def mock_session():
    """SQLAlchemy AsyncSession mock"""
    session = AsyncMock(spec=AsyncSession)
    return session


# ---------------------------------------------------------------------------
# 비밀번호 해싱 테스트
# ---------------------------------------------------------------------------


def test_hash_password(auth_service):
    """비밀번호를 bcrypt로 해싱한다"""
    hashed = auth_service.hash_password("password123")
    assert hashed != "password123"
    assert len(hashed) > 20


def test_verify_password_correct(auth_service):
    """올바른 비밀번호 검증 성공"""
    hashed = auth_service.hash_password("password123")
    assert auth_service.verify_password("password123", hashed) is True


def test_verify_password_wrong(auth_service):
    """잘못된 비밀번호 검증 실패"""
    hashed = auth_service.hash_password("password123")
    assert auth_service.verify_password("wrongpassword", hashed) is False


# ---------------------------------------------------------------------------
# JWT 토큰 테스트
# ---------------------------------------------------------------------------


def test_create_access_token_returns_jwt(auth_service):
    """access token을 JWT 문자열로 반환한다"""
    user_id = str(uuid.uuid4())
    token = auth_service.create_access_token(user_id, "test@example.com")
    # JWT는 점(.)으로 구분된 3개 파트
    parts = token.split(".")
    assert len(parts) == 3


def test_decode_access_token_valid(auth_service):
    """유효한 JWT를 디코딩한다"""
    user_id = str(uuid.uuid4())
    email = "test@example.com"
    token = auth_service.create_access_token(user_id, email)
    payload = auth_service.decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == email


def test_decode_access_token_expired(auth_service):
    """만료된 JWT 디코딩 시 예외 발생"""
    from fastapi import HTTPException
    user_id = str(uuid.uuid4())
    # 1초 전에 만료된 토큰 생성
    expired_token = auth_service.create_access_token(
        user_id, "test@example.com", expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(HTTPException) as exc_info:
        auth_service.decode_access_token(expired_token)
    assert exc_info.value.status_code == 401


def test_create_refresh_token(auth_service):
    """refresh token은 비어있지 않은 문자열"""
    token = auth_service.create_refresh_token()
    assert isinstance(token, str)
    assert len(token) > 10


# ---------------------------------------------------------------------------
# 회원 가입 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_user(auth_service, mock_session):
    """회원 가입 시 User와 RefreshToken이 생성된다"""
    # execute()가 이메일 중복 검사에서 빈 결과를 반환하도록 설정
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # 이메일 없음
    mock_session.execute.return_value = mock_result

    user, access_token, refresh_token = await auth_service.register(
        session=mock_session,
        email="new@example.com",
        password="password123",
        display_name="새 사용자",
    )

    assert isinstance(user, User)
    assert user.email == "new@example.com"
    assert user.display_name == "새 사용자"
    assert isinstance(access_token, str)
    assert isinstance(refresh_token, str)
    # DB에 add가 2번 호출 (User + RefreshToken)
    assert mock_session.add.call_count == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_register_duplicate_email_raises(auth_service, mock_session):
    """중복 이메일로 가입 시 409 예외 발생"""
    from fastapi import HTTPException

    # 이미 존재하는 User 반환
    existing_user = User()
    existing_user.email = "existing@example.com"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user
    mock_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register(
            session=mock_session,
            email="existing@example.com",
            password="password123",
            display_name="중복 사용자",
        )
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# 로그인 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(auth_service, mock_session):
    """올바른 자격증명으로 로그인 성공"""
    # 해싱된 비밀번호를 가진 User 생성
    user = User()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.password_hash = auth_service.hash_password("password123")
    user.display_name = "테스트 사용자"
    user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = mock_result

    result_user, access_token, refresh_token = await auth_service.login(
        session=mock_session,
        email="user@example.com",
        password="password123",
    )

    assert result_user.email == "user@example.com"
    assert isinstance(access_token, str)
    assert isinstance(refresh_token, str)


@pytest.mark.asyncio
async def test_login_wrong_password(auth_service, mock_session):
    """잘못된 비밀번호로 로그인 시 401 예외"""
    from fastapi import HTTPException

    user = User()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.password_hash = auth_service.hash_password("password123")
    user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            session=mock_session,
            email="user@example.com",
            password="wrongpassword",
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(auth_service, mock_session):
    """존재하지 않는 이메일로 로그인 시 401 예외"""
    from fastapi import HTTPException

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login(
            session=mock_session,
            email="nonexistent@example.com",
            password="password123",
        )
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Refresh Token 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_rotation(auth_service, mock_session):
    """refresh token 갱신 시 새 토큰 쌍 반환 (rotation)"""
    import hashlib
    raw_token = "valid-refresh-token-string"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # 유효한 RefreshToken 레코드
    token_record = RefreshToken()
    token_record.id = uuid.uuid4()
    token_record.user_id = uuid.uuid4()
    token_record.token_hash = token_hash
    token_record.expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7)
    token_record.is_revoked = False

    # User 레코드
    user = User()
    user.id = token_record.user_id
    user.email = "user@example.com"
    user.is_active = True

    # execute() 첫 번째 호출: refresh token 조회
    # execute() 두 번째 호출: user 조회
    mock_result_token = MagicMock()
    mock_result_token.scalar_one_or_none.return_value = token_record
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = user
    mock_session.execute.side_effect = [mock_result_token, mock_result_user]

    new_access, new_refresh = await auth_service.refresh(
        session=mock_session,
        refresh_token_str=raw_token,
    )

    assert isinstance(new_access, str)
    assert isinstance(new_refresh, str)
    # 기존 토큰은 폐기됨
    assert token_record.is_revoked is True
    # 새 RefreshToken이 DB에 추가됨
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_logout_revokes_token(auth_service, mock_session):
    """로그아웃 시 refresh token 폐기"""
    import hashlib
    raw_token = "logout-token-string"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    token_record = RefreshToken()
    token_record.id = uuid.uuid4()
    token_record.token_hash = token_hash
    token_record.is_revoked = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = token_record
    mock_session.execute.return_value = mock_result

    await auth_service.logout(session=mock_session, refresh_token_str=raw_token)

    assert token_record.is_revoked is True
    mock_session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# 비밀번호 유효성 검사 테스트
# ---------------------------------------------------------------------------


def test_password_validation_min_length():
    """비밀번호 최소 8자 검증 (Pydantic 스키마 레벨)"""
    from pydantic import ValidationError

    from backend.schemas.auth import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(email="test@test.com", password="short1", display_name="테스트")


def test_password_validation_letter_and_digit():
    """비밀번호는 영문자와 숫자를 모두 포함해야 함"""
    from pydantic import ValidationError

    from backend.schemas.auth import RegisterRequest

    # 숫자 없음
    with pytest.raises(ValidationError):
        RegisterRequest(email="test@test.com", password="onlyletters", display_name="테스트")

    # 영문자 없음
    with pytest.raises(ValidationError):
        RegisterRequest(email="test@test.com", password="12345678", display_name="테스트")
