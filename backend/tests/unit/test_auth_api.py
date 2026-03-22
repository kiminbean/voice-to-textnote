"""
SPEC-TEAM-001: Auth API 엔드포인트 단위 테스트 (TDD RED Phase)

테스트 대상:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client():
    """
    인증 테스트용 TestClient
    - DB 세션을 mock으로 대체
    - 모델 로드 없이 앱 생성
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.dependencies import get_db_session

    async def mock_db_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_db_session

    with patch("backend.app.main.WhisperEngine"):
        with patch("backend.app.main.DiarizationEngine"):
            with patch("backend.app.lifecycle.validate_startup", new_callable=AsyncMock):
                with patch("backend.app.lifecycle.cleanup_shutdown", new_callable=AsyncMock):
                    yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 회원 가입 테스트
# ---------------------------------------------------------------------------


def test_register_success_201(auth_client):
    """회원 가입 성공 시 201 + TokenResponse 반환"""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "newuser@example.com"
    mock_user.display_name = "새 사용자"
    mock_user.is_active = True
    mock_user.created_at = datetime.now(UTC).replace(tzinfo=None)

    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.register = AsyncMock(
            return_value=(mock_user, "access-token-string", "refresh-token-string")
        )
        response = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "password123",
                "display_name": "새 사용자",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_409(auth_client):
    """중복 이메일 가입 시 409 반환"""
    from fastapi import HTTPException

    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.register = AsyncMock(
            side_effect=HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
        )
        response = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "password123",
                "display_name": "중복",
            },
        )

    assert response.status_code == 409


def test_register_weak_password_422(auth_client):
    """너무 짧은 비밀번호로 가입 시 422 반환"""
    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "short",
            "display_name": "테스트",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 로그인 테스트
# ---------------------------------------------------------------------------


def test_login_success_200(auth_client):
    """로그인 성공 시 200 + TokenResponse 반환"""
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "user@example.com"

    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.login = AsyncMock(
            return_value=(mock_user, "access-token", "refresh-token")
        )
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "password123"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_wrong_credentials_401(auth_client):
    """잘못된 자격증명으로 로그인 시 401 반환"""
    from fastapi import HTTPException

    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.login = AsyncMock(
            side_effect=HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        )
        response = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrongpassword"},
        )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Refresh Token 테스트
# ---------------------------------------------------------------------------


def test_refresh_success(auth_client):
    """refresh token 갱신 성공 시 200 + 새 TokenResponse"""
    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.refresh = AsyncMock(
            return_value=("new-access-token", "new-refresh-token")
        )
        response = auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid-refresh-token"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "new-access-token"


# ---------------------------------------------------------------------------
# 로그아웃 테스트
# ---------------------------------------------------------------------------


def test_logout_success_204(auth_client):
    """로그아웃 성공 시 204 반환"""
    with patch("backend.app.api.v1.auth._auth_service") as mock_svc:
        mock_svc.logout = AsyncMock(return_value=None)
        response = auth_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "some-refresh-token"},
        )

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# /me 엔드포인트 테스트
# ---------------------------------------------------------------------------


def test_get_me_authenticated(auth_client):
    """유효한 JWT로 /me 조회 성공"""
    from backend.app.dependencies import get_current_user

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "me@example.com"
    mock_user.display_name = "나"
    mock_user.is_active = True
    mock_user.created_at = datetime.now(UTC).replace(tzinfo=None)

    async def mock_get_user():
        return mock_user

    from backend.app.main import app
    app.dependency_overrides[get_current_user] = mock_get_user

    response = auth_client.get("/api/v1/auth/me")

    app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"


def test_get_me_unauthenticated_401(auth_client):
    """Authorization 헤더 없이 /me 조회 시 401"""
    # get_current_user 오버라이드 없이 직접 호출
    response = auth_client.get("/api/v1/auth/me")
    # 인증 없이 요청하면 401
    assert response.status_code in (401, 403)
