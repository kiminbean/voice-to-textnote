"""SPEC-REFACTOR-001 Phase 1: 에러 헬퍼 및 예외 계층 테스트"""

import pytest

from backend.app.errors import (
    conflict,
    forbidden,
    not_found,
    rate_limit,
    unauthorized,
)
from backend.app.exceptions import (
    AudioProcessingError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PipelineError,
    RateLimitError,
    StorageError,
    UnauthorizedError,
    VoiceNoteError,
)


class TestExceptionHierarchy:
    """예외 계층 구조 테스트"""

    def test_not_found_error_extends_voicenote_error(self):
        """NotFoundError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(NotFoundError, VoiceNoteError)

    def test_unauthorized_error_extends_voicenote_error(self):
        """UnauthorizedError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(UnauthorizedError, VoiceNoteError)

    def test_forbidden_error_extends_voicenote_error(self):
        """ForbiddenError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(ForbiddenError, VoiceNoteError)

    def test_conflict_error_extends_voicenote_error(self):
        """ConflictError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(ConflictError, VoiceNoteError)

    def test_rate_limit_error_extends_voicenote_error(self):
        """RateLimitError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(RateLimitError, VoiceNoteError)

    def test_audio_processing_error_extends_voicenote_error(self):
        """AudioProcessingError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(AudioProcessingError, VoiceNoteError)

    def test_storage_error_extends_voicenote_error(self):
        """StorageError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(StorageError, VoiceNoteError)

    def test_pipeline_error_extends_voicenote_error(self):
        """PipelineError가 VoiceNoteError를 상속하는지 확인"""
        assert issubclass(PipelineError, VoiceNoteError)


class TestExceptionAttributes:
    """예외 속성 테스트"""

    def test_not_found_error_has_correct_status_code(self):
        """NotFoundError가 올바른 상태 코드를 가지는지 확인"""
        err = NotFoundError(message="test", error_code="NOT_FOUND", status_code=404)
        assert err.status_code == 404
        assert err.error_code == "NOT_FOUND"
        assert err.message == "test"

    def test_unauthorized_error_has_correct_status_code(self):
        """UnauthorizedError가 올바른 상태 코드를 가지는지 확인"""
        err = UnauthorizedError(message="test", error_code="UNAUTHORIZED", status_code=401)
        assert err.status_code == 401
        assert err.error_code == "UNAUTHORIZED"

    def test_forbidden_error_has_correct_status_code(self):
        """ForbiddenError가 올바른 상태 코드를 가지는지 확인"""
        err = ForbiddenError(message="test", error_code="FORBIDDEN", status_code=403)
        assert err.status_code == 403
        assert err.error_code == "FORBIDDEN"

    def test_conflict_error_has_correct_status_code(self):
        """ConflictError가 올바른 상태 코드를 가지는지 확인"""
        err = ConflictError(message="test", error_code="CONFLICT", status_code=409)
        assert err.status_code == 409
        assert err.error_code == "CONFLICT"

    def test_rate_limit_error_has_correct_status_code(self):
        """RateLimitError가 올바른 상태 코드를 가지는지 확인"""
        err = RateLimitError(message="test", error_code="RATE_LIMIT", status_code=429)
        assert err.status_code == 429
        assert err.error_code == "RATE_LIMIT"


class TestErrorHelpers:
    """에러 헬퍼 함수 테스트"""

    def test_not_found_raises_not_found_error(self):
        """not_found()가 NotFoundError를 발생시키는지 확인"""
        with pytest.raises(NotFoundError):
            not_found()

    def test_not_found_with_custom_message(self):
        """not_found()가 커스텀 메시지로 에러를 발생시키는지 확인"""
        with pytest.raises(NotFoundError) as exc_info:
            not_found("사용자를 찾을 수 없습니다")
        assert "사용자를 찾을 수 없습니다" in str(exc_info.value)

    def test_unauthorized_raises_unauthorized_error(self):
        """unauthorized()가 UnauthorizedError를 발생시키는지 확인"""
        with pytest.raises(UnauthorizedError):
            unauthorized()

    def test_forbidden_raises_forbidden_error(self):
        """forbidden()가 ForbiddenError를 발생시키는지 확인"""
        with pytest.raises(ForbiddenError):
            forbidden()

    def test_conflict_raises_conflict_error(self):
        """conflict()가 ConflictError를 발생시키는지 확인"""
        with pytest.raises(ConflictError):
            conflict("이미 존재합니다")

    def test_rate_limit_raises_rate_limit_error(self):
        """rate_limit()가 RateLimitError를 발생시키는지 확인"""
        with pytest.raises(RateLimitError):
            rate_limit()

    def test_all_helpers_raise_voicenote_error(self):
        """모든 헬퍼가 VoiceNoteError 서브클래스를 발생시키는지 확인"""
        for helper, _expected_cls in [
            (not_found, NotFoundError),
            (unauthorized, UnauthorizedError),
            (forbidden, ForbiddenError),
            (conflict, ConflictError),
            (rate_limit, RateLimitError),
        ]:
            with pytest.raises(VoiceNoteError):
                if helper == conflict:
                    helper("test")
                else:
                    helper()

    def test_not_found_with_custom_error_code(self):
        """not_found()가 커스텀 error_code를 지원하는지 확인"""
        with pytest.raises(NotFoundError) as exc_info:
            not_found(error_code="USER_NOT_FOUND")
        assert exc_info.value.error_code == "USER_NOT_FOUND"

    def test_unauthorized_with_custom_error_code(self):
        """unauthorized()가 커스텀 error_code를 지원하는지 확인"""
        with pytest.raises(UnauthorizedError) as exc_info:
            unauthorized(error_code="INVALID_TOKEN")
        assert exc_info.value.error_code == "INVALID_TOKEN"

    def test_forbidden_with_custom_error_code(self):
        """forbidden()가 커스텀 error_code를 지원하는지 확인"""
        with pytest.raises(ForbiddenError) as exc_info:
            forbidden(error_code="INSUFFICIENT_PERMISSIONS")
        assert exc_info.value.error_code == "INSUFFICIENT_PERMISSIONS"

    def test_conflict_with_custom_error_code(self):
        """conflict()가 커스텀 error_code를 지원하는지 확인"""
        with pytest.raises(ConflictError) as exc_info:
            conflict("이미 존재합니다", error_code="DUPLICATE_RESOURCE")
        assert exc_info.value.error_code == "DUPLICATE_RESOURCE"

    def test_rate_limit_with_custom_error_code(self):
        """rate_limit()가 커스텀 error_code를 지원하는지 확인"""
        with pytest.raises(RateLimitError) as exc_info:
            rate_limit(error_code="DAILY_LIMIT_EXCEEDED")
        assert exc_info.value.error_code == "DAILY_LIMIT_EXCEEDED"
