"""
REQ-ERR-007: Settings 범위 유효성 검사 테스트
"""

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


class TestMaxConcurrentJobsValidation:
    """max_concurrent_jobs 범위 유효성 검사 (1-10)"""

    def test_valid_min_value(self):
        """max_concurrent_jobs=1은 유효해야 한다"""
        settings = Settings(max_concurrent_jobs=1)
        assert settings.max_concurrent_jobs == 1

    def test_valid_max_value(self):
        """max_concurrent_jobs=10은 유효해야 한다"""
        settings = Settings(max_concurrent_jobs=10)
        assert settings.max_concurrent_jobs == 10

    def test_valid_middle_value(self):
        """max_concurrent_jobs=5는 유효해야 한다"""
        settings = Settings(max_concurrent_jobs=5)
        assert settings.max_concurrent_jobs == 5

    def test_default_value_is_valid(self):
        """기본값 max_concurrent_jobs=3은 유효해야 한다"""
        settings = Settings()
        assert 1 <= settings.max_concurrent_jobs <= 10

    def test_zero_raises_validation_error(self):
        """max_concurrent_jobs=0은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_concurrent_jobs=0)
        assert "max_concurrent_jobs" in str(exc_info.value)

    def test_negative_raises_validation_error(self):
        """max_concurrent_jobs=-1은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_concurrent_jobs=-1)
        assert "max_concurrent_jobs" in str(exc_info.value)

    def test_eleven_raises_validation_error(self):
        """max_concurrent_jobs=11은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_concurrent_jobs=11)
        assert "max_concurrent_jobs" in str(exc_info.value)


class TestMaxFileSizeMbValidation:
    """max_file_size_mb 범위 유효성 검사 (1-2000)"""

    def test_valid_min_value(self):
        """max_file_size_mb=1은 유효해야 한다"""
        settings = Settings(max_file_size_mb=1)
        assert settings.max_file_size_mb == 1

    def test_valid_max_value(self):
        """max_file_size_mb=2000은 유효해야 한다"""
        settings = Settings(max_file_size_mb=2000)
        assert settings.max_file_size_mb == 2000

    def test_valid_middle_value(self):
        """max_file_size_mb=500은 유효해야 한다"""
        settings = Settings(max_file_size_mb=500)
        assert settings.max_file_size_mb == 500

    def test_default_value_is_valid(self):
        """기본값 max_file_size_mb=500은 유효해야 한다"""
        settings = Settings()
        assert 1 <= settings.max_file_size_mb <= 2000

    def test_zero_raises_validation_error(self):
        """max_file_size_mb=0은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_file_size_mb=0)
        assert "max_file_size_mb" in str(exc_info.value)

    def test_negative_raises_validation_error(self):
        """max_file_size_mb=-100은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_file_size_mb=-100)
        assert "max_file_size_mb" in str(exc_info.value)

    def test_over_max_raises_validation_error(self):
        """max_file_size_mb=2001은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(max_file_size_mb=2001)
        assert "max_file_size_mb" in str(exc_info.value)


class TestRateLimitPerMinuteValidation:
    """rate_limit_per_minute 범위 유효성 검사 (1-1000)"""

    def test_valid_min_value(self):
        """rate_limit_per_minute=1은 유효해야 한다"""
        settings = Settings(rate_limit_per_minute=1)
        assert settings.rate_limit_per_minute == 1

    def test_valid_max_value(self):
        """rate_limit_per_minute=1000은 유효해야 한다"""
        settings = Settings(rate_limit_per_minute=1000)
        assert settings.rate_limit_per_minute == 1000

    def test_valid_middle_value(self):
        """rate_limit_per_minute=60은 유효해야 한다"""
        settings = Settings(rate_limit_per_minute=60)
        assert settings.rate_limit_per_minute == 60

    def test_default_value_is_valid(self):
        """기본값 rate_limit_per_minute=60은 유효해야 한다"""
        settings = Settings()
        assert 1 <= settings.rate_limit_per_minute <= 1000

    def test_zero_raises_validation_error(self):
        """rate_limit_per_minute=0은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(rate_limit_per_minute=0)
        assert "rate_limit_per_minute" in str(exc_info.value)

    def test_negative_raises_validation_error(self):
        """rate_limit_per_minute=-10은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(rate_limit_per_minute=-10)
        assert "rate_limit_per_minute" in str(exc_info.value)

    def test_over_max_raises_validation_error(self):
        """rate_limit_per_minute=1001은 유효성 검사 오류를 발생시켜야 한다"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(rate_limit_per_minute=1001)
        assert "rate_limit_per_minute" in str(exc_info.value)


class TestExistingDefaultsStillWork:
    """기존 기본값들이 여전히 유효한지 확인 (회귀 방지)"""

    def test_default_settings_are_valid(self):
        """기본 Settings 생성이 실패하지 않아야 한다"""
        # 기본값으로 Settings 생성이 성공해야 함
        settings = Settings()
        assert settings is not None

    def test_default_max_concurrent_jobs(self):
        """기본 max_concurrent_jobs=3은 유효 범위(1-10)에 있어야 한다"""
        settings = Settings()
        assert settings.max_concurrent_jobs == 3

    def test_default_max_file_size_mb(self):
        """기본 max_file_size_mb=500은 유효 범위(1-2000)에 있어야 한다"""
        settings = Settings()
        assert settings.max_file_size_mb == 500

    def test_default_rate_limit_per_minute(self):
        """기본 rate_limit_per_minute=60은 유효 범위(1-1000)에 있어야 한다"""
        settings = Settings()
        assert settings.rate_limit_per_minute == 60
