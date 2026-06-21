"""
config.py 모듈 테스트
커버리지: 현재 89% → 목표 95%+
누락 라인: 208-210, 218-219, 227, 229, 237, 239, 244, 250, 255, 259, 263, 267

테스트 대상:
- parse_list_from_string (라인 208-210)
- validate_environment (라인 218-219)
- validate_cors_allow_methods (라인 227, 229)
- validate_cors_allow_origins (라인 237, 239, 244)
- validate_production_security (라인 250)
- max_file_size_bytes property (라인 255)
- max_duration_seconds property (라인 259)
- chunk_duration_ms property (라인 263)
- chunk_overlap_ms property (라인 267)
"""

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


class TestParseListFromString:
    """parse_list_from_string 메서드 테스트"""

    def test_parse_empty_string(self):
        """빈 문자열이면 빈 리스트 반환 (라인 208-210)"""
        result = Settings.parse_list_from_string("")
        assert result == []

    def test_parse_whitespace_string(self):
        """공백만 있는 문자열도 빈 리스트"""
        result = Settings.parse_list_from_string("   ")
        assert result == []

    def test_parse_single_item(self):
        """단일 항목 파싱"""
        result = Settings.parse_list_from_string("key1")
        assert result == ["key1"]

    def test_parse_multiple_items(self):
        """여러 항목 파싱"""
        result = Settings.parse_list_from_string("key1,key2,key3")
        assert result == ["key1", "key2", "key3"]

    def test_parse_with_spaces(self):
        """공백 포함 문자열 파싱"""
        result = Settings.parse_list_from_string("key1, key2 , key3")
        assert result == ["key1", "key2", "key3"]

    def test_parse_already_list(self):
        """이미 리스트인 경우 그대로 반환"""
        result = Settings.parse_list_from_string(["key1", "key2"])
        assert result == ["key1", "key2"]


class TestValidateEnvironment:
    """environment 검증 테스트"""

    def test_valid_environments(self):
        """유효한 환경값"""
        for env in ["development", "staging", "production"]:
            # 환경 변수를 설정하여 검증
            import os

            old_val = os.environ.get("ENVIRONMENT")
            old_api = os.environ.get("API_KEYS")
            old_jwt = os.environ.get("JWT_SECRET")
            try:
                os.environ["ENVIRONMENT"] = env
                # production 환경에서는 API_KEYS/JWT_SECRET 필요
                if env == "production":
                    os.environ["API_KEYS"] = "test-key"
                    os.environ["JWT_SECRET"] = "x" * 48
                # Settings 생성 시 검증됨
                settings = Settings()
                assert settings.environment == env
            finally:
                if old_val:
                    os.environ["ENVIRONMENT"] = old_val
                else:
                    os.environ.pop("ENVIRONMENT", None)
                if old_api:
                    os.environ["API_KEYS"] = old_api
                else:
                    os.environ.pop("API_KEYS", None)
                if old_jwt:
                    os.environ["JWT_SECRET"] = old_jwt
                else:
                    os.environ.pop("JWT_SECRET", None)

    def test_invalid_environment(self):
        """유효하지 않은 환경값 (라인 218-219)"""
        import os

        old_val = os.environ.get("ENVIRONMENT")
        old_api = os.environ.get("API_KEYS")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["ENVIRONMENT"] = "invalid_env"
            os.environ["API_KEYS"] = "test-key"
            os.environ["JWT_SECRET"] = "x" * 48
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "environment는 다음 중 하나여야 합니다" in str(exc_info.value)
        finally:
            if old_val:
                os.environ["ENVIRONMENT"] = old_val
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_api:
                os.environ["API_KEYS"] = old_api
            else:
                os.environ.pop("API_KEYS", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)

    def test_environment_normalization(self):
        """환경값 정규화 (라인 216)"""
        import os

        old_val = os.environ.get("ENVIRONMENT")
        old_api = os.environ.get("API_KEYS")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["ENVIRONMENT"] = "  Development  "
            os.environ["API_KEYS"] = "test-key"
            os.environ["JWT_SECRET"] = "x" * 48
            settings = Settings()
            assert settings.environment == "development"
        finally:
            if old_val:
                os.environ["ENVIRONMENT"] = old_val
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_api:
                os.environ["API_KEYS"] = old_api
            else:
                os.environ.pop("API_KEYS", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)


class TestValidateCorsAllowMethods:
    """CORS 허용 메서드 검증 테스트"""

    def test_empty_methods_raises_error(self):
        """빈 메서드 목록은 에러 (라인 227)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_allow_methods=[])
        assert "cors_allow_methods는 최소 1개 이상의 메서드를 포함해야 합니다" in str(
            exc_info.value
        )

    def test_wildcard_raises_error(self):
        """와일드카드(*)는 에러 (라인 229)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_allow_methods=["*"])
        assert "cors_allow_methods에 와일드카드(*)를 사용할 수 없습니다" in str(exc_info.value)

    def test_valid_methods(self):
        """유효한 메서드 목록"""
        settings = Settings(cors_allow_methods=["GET", "POST"])
        assert settings.cors_allow_methods == ["GET", "POST"]

    def test_methods_normalization(self):
        """메서드 대문자 정규화 (라인 225)"""
        settings = Settings(cors_allow_methods=["get", "post"])
        assert settings.cors_allow_methods == ["GET", "POST"]


class TestValidateCorsAllowOrigins:
    """CORS 허용 origin 검증 테스트"""

    def test_empty_origins_raises_error(self):
        """빈 origin 목록은 에러 (라인 237)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_allow_origins=[])
        assert "cors_allow_origins는 최소 1개 이상의 origin을 포함해야 합니다" in str(
            exc_info.value
        )

    def test_wildcard_with_credentials_raises_error(self):
        """allow_credentials=True일 때 와일드카드(*)는 에러 (라인 239)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_allow_origins=["*"], allow_credentials=True)
        assert "cors_allow_origins에 '*'를 사용할 수 없습니다" in str(exc_info.value)

    def test_invalid_origin_format(self):
        """유효하지 않은 origin 형식 (라인 244)"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(cors_allow_origins=["invalid-origin"])
        assert "유효하지 않은 origin 형식입니다" in str(exc_info.value)

    def test_valid_origins(self):
        """유효한 origin 목록"""
        settings = Settings(cors_allow_origins=["http://localhost:3000", "https://example.com"])
        assert len(settings.cors_allow_origins) == 2


class TestValidateProductionSecurity:
    """production 보안 검증 테스트"""

    def test_production_without_api_keys_raises_error(self):
        """production 환경에서 API_KEYS 없으면 에러 (라인 250)"""
        import os

        old_val = os.environ.get("API_KEYS")
        old_env = os.environ.get("ENVIRONMENT")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ.pop("API_KEYS", None)
            os.environ["ENVIRONMENT"] = "production"
            os.environ["JWT_SECRET"] = "x" * 48
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "production 환경에서는 API_KEYS를 반드시 설정해야 합니다" in str(exc_info.value)
        finally:
            if old_val:
                os.environ["API_KEYS"] = old_val
            else:
                os.environ.pop("API_KEYS", None)
            if old_env:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)

    def test_production_without_jwt_secret_raises_error(self):
        """production 환경에서 JWT_SECRET 없으면 에러"""
        import os

        old_api = os.environ.get("API_KEYS")
        old_env = os.environ.get("ENVIRONMENT")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["API_KEYS"] = "test-key"
            os.environ["ENVIRONMENT"] = "production"
            os.environ.pop("JWT_SECRET", None)
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "production 환경에서는 JWT_SECRET을 반드시 설정해야 합니다" in str(
                exc_info.value
            )
        finally:
            if old_api:
                os.environ["API_KEYS"] = old_api
            else:
                os.environ.pop("API_KEYS", None)
            if old_env:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)

    def test_production_with_short_jwt_secret_raises_error(self):
        """production 환경에서 JWT_SECRET이 짧으면 에러"""
        import os

        old_api = os.environ.get("API_KEYS")
        old_env = os.environ.get("ENVIRONMENT")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["API_KEYS"] = "test-key"
            os.environ["ENVIRONMENT"] = "production"
            os.environ["JWT_SECRET"] = "short-secret"
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "JWT_SECRET은 최소 32자 이상" in str(exc_info.value)
        finally:
            if old_api:
                os.environ["API_KEYS"] = old_api
            else:
                os.environ.pop("API_KEYS", None)
            if old_env:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)

    def test_development_without_api_keys_ok(self):
        """development 환경에서는 API_KEYS 없어도 OK"""
        import os

        old_val = os.environ.get("API_KEYS")
        old_env = os.environ.get("ENVIRONMENT")
        try:
            os.environ.pop("API_KEYS", None)
            os.environ["ENVIRONMENT"] = "development"
            # 에러 없이 생성됨
            settings = Settings()
            assert settings.environment == "development"
        finally:
            if old_val:
                os.environ["API_KEYS"] = old_val
            else:
                os.environ.pop("API_KEYS", None)
            if old_env:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)


class TestProperties:
    """속성 계산 테스트"""

    def test_max_file_size_bytes(self):
        """max_file_size_bytes 속성 (라인 255)"""
        settings = Settings(max_file_size_mb=500)
        assert settings.max_file_size_bytes == 500 * 1024 * 1024

    def test_max_duration_seconds(self):
        """max_duration_seconds 속성 (라인 259)"""
        settings = Settings(max_duration_hours=4)
        assert settings.max_duration_seconds == 4 * 3600

    def test_chunk_duration_ms(self):
        """chunk_duration_ms 속성 (라인 263)"""
        settings = Settings(chunk_duration_minutes=30)
        assert settings.chunk_duration_ms == 30 * 60 * 1000

    def test_chunk_overlap_ms(self):
        """chunk_overlap_ms 속성 (라인 267)"""
        settings = Settings(chunk_overlap_seconds=5)
        assert settings.chunk_overlap_ms == 5 * 1000


class TestSettingsIntegration:
    """Settings 통합 테스트"""

    def test_default_values(self):
        """기본값 설정 확인"""
        settings = Settings()
        assert settings.environment == "development"
        assert settings.max_file_size_mb == 500
        assert settings.max_concurrent_jobs == 3
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_custom_values(self):
        """사용자 정의값 설정"""
        import os

        old_api = os.environ.get("API_KEYS")
        old_env = os.environ.get("ENVIRONMENT")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["API_KEYS"] = "test-key"
            os.environ["ENVIRONMENT"] = "production"
            os.environ["JWT_SECRET"] = "x" * 48
            settings = Settings(max_file_size_mb=1000, max_concurrent_jobs=5)
            assert settings.max_file_size_mb == 1000
            assert settings.max_concurrent_jobs == 5
            assert settings.environment == "production"
        finally:
            if old_api:
                os.environ["API_KEYS"] = old_api
            else:
                os.environ.pop("API_KEYS", None)
            if old_env:
                os.environ["ENVIRONMENT"] = old_env
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt
            else:
                os.environ.pop("JWT_SECRET", None)

    def test_field_validators(self):
        """필드 검증기 통합 테스트"""
        import os

        old_env = os.environ.get("ENVIRONMENT")
        old_jwt = os.environ.get("JWT_SECRET")
        try:
            os.environ["ENVIRONMENT"] = "production"
            os.environ["API_KEYS"] = "test-key"
            os.environ["JWT_SECRET"] = "x" * 48
            settings = Settings(
                environment="production",
                jwt_secret="x" * 48,
                cors_allow_origins=["https://example.com"],
                cors_allow_methods=["GET", "POST"],
            )
            assert settings.environment == "production"
            assert len(settings.cors_allow_origins) == 1
            assert len(settings.cors_allow_methods) == 2
        finally:
            if old_env:
                os.environ["ENVIRONMENT"] = old_env  # pragma: no cover
            else:
                os.environ.pop("ENVIRONMENT", None)
            if old_jwt:
                os.environ["JWT_SECRET"] = old_jwt  # pragma: no cover
            else:
                os.environ.pop("JWT_SECRET", None)
