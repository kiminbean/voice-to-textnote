"""
SPEC-MOBILE-004 T-006: PushService Firebase 초기화 프로덕션화

REQ-MOBILE-002-06: firebase_credentials_path 설정 시 실제 firebase_admin 사용
- credentials 없으면 MOCK 모드 유지 (기존 동작)
- credentials 있으면 firebase_admin.initialize_app() 호출
"""

from unittest.mock import MagicMock, patch

from backend.services.push_service import PushService


class TestFirebaseInitialization:
    """T-006: _ensure_firebase_initialized 프로덕션화 테스트"""

    def test_mock_mode_when_no_credentials(self):
        """firebase_credentials_path=None이면 MOCK 모드 유지"""
        with patch("backend.services.push_service.settings") as mock_settings:
            mock_settings.firebase_credentials_path = None
            service = PushService()
            service._ensure_firebase_initialized()
            assert service._firebase_initialized is True
            assert service._is_mock_mode is True

    def test_mock_mode_when_empty_credentials(self):
        """firebase_credentials_path=''이면 MOCK 모드 유지"""
        with patch("backend.services.push_service.settings") as mock_settings:
            mock_settings.firebase_credentials_path = ""
            service = PushService()
            service._ensure_firebase_initialized()
            assert service._is_mock_mode is True

    def test_real_mode_when_credentials_set(self):
        """firebase_credentials_path 설정 시 실제 firebase_admin 초기화 시도"""
        with (
            patch("backend.services.push_service.settings") as mock_settings,
            patch("builtins.__import__") as mock_import,
        ):
            mock_settings.firebase_credentials_path = "/path/to/creds.json"

            mock_firebase_admin = MagicMock()
            mock_credentials_module = MagicMock()
            mock_firebase_admin.credentials = mock_credentials_module
            mock_import.return_value = mock_firebase_admin

            service = PushService()
            service._ensure_firebase_initialized()

            assert service._firebase_initialized is True
            assert service._is_mock_mode is False

    def test_real_mode_fallback_to_mock_on_import_error(self):
        """firebase_admin 임포트 실패 시 MOCK 모드로 폴백"""
        with patch("backend.services.push_service.settings") as mock_settings:
            mock_settings.environment = "development"
            mock_settings.firebase_credentials_path = "/path/to/creds.json"
            service = PushService()
            service._ensure_firebase_initialized()
            assert service._is_mock_mode is True

    def test_production_raises_on_firebase_initialization_failure(self):
        """production에서는 Firebase 초기화 실패를 MOCK으로 숨기지 않음"""
        with patch("backend.services.push_service.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.firebase_credentials_path = "/path/to/creds.json"
            service = PushService()

            try:
                service._ensure_firebase_initialized()
            except RuntimeError as exc:
                assert "Firebase initialization failed in production" in str(exc)
            else:  # pragma: no cover
                raise AssertionError("production Firebase initialization failure was hidden")

    def test_real_mode_skips_reinit(self):
        """이미 초기화됐으면 재초기화 안 함"""
        with patch("backend.services.push_service.settings") as mock_settings:
            mock_settings.firebase_credentials_path = None
            service = PushService()
            service._firebase_initialized = True
            service._is_mock_mode = True
            service._ensure_firebase_initialized()
            assert service._is_mock_mode is True
