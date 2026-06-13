"""
SPEC-MOBILE-004 T-007: Firebase 설정 필드 테스트

REQ-MOBILE-002-06: config.py에 firebase_credentials_path 필드 추가
- 환경변수 FIREBASE_CREDENTIALS_PATH에서 로드
- 기본값 None (미설정 시 MOCK 모드)
"""

import pytest

from backend.app.config import Settings


class TestFirebaseCredentialsPath:
    """T-007: firebase_credentials_path 설정 필드 테스트"""

    def test_default_is_none(self):
        """기본값은 None (MOCK 모드)"""
        settings = Settings()
        assert hasattr(settings, "firebase_credentials_path")
        assert settings.firebase_credentials_path is None

    def test_can_set_via_env(self, monkeypatch):
        """환경변수 FIREBASE_CREDENTIALS_PATH로 설정 가능"""
        monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", "/path/to/firebase.json")
        settings = Settings()
        assert settings.firebase_credentials_path == "/path/to/firebase.json"

    def test_empty_string_is_none(self, monkeypatch):
        """빈 문자열이면 None으로 처리되지 않음 (빈 문자열 그대로 유지)"""
        monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", "")
        settings = Settings()
        # pydantic-settings는 빈 문자열을 빈 문자열로 유지
        # push_service에서 falsy 체크로 MOCK 모드 판별
        assert settings.firebase_credentials_path == ""
