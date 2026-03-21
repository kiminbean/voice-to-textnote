"""
REQ-ERR-001, REQ-ERR-002: 도메인 예외 계층 구조 테스트
"""

import pytest

from backend.app.exceptions import (
    AudioProcessingError,
    PipelineError,
    StorageError,
    VoiceNoteError,
)


class TestVoiceNoteError:
    """VoiceNoteError 기본 예외 클래스 테스트"""

    def test_voicenote_error_is_exception(self):
        """VoiceNoteError는 Exception을 상속해야 한다"""
        assert issubclass(VoiceNoteError, Exception)

    def test_voicenote_error_has_error_code(self):
        """VoiceNoteError는 error_code 속성을 가져야 한다"""
        exc = VoiceNoteError(error_code="ERR_001", message="테스트 오류", status_code=500)
        assert exc.error_code == "ERR_001"

    def test_voicenote_error_has_message(self):
        """VoiceNoteError는 message 속성을 가져야 한다"""
        exc = VoiceNoteError(error_code="ERR_001", message="테스트 오류", status_code=500)
        assert exc.message == "테스트 오류"

    def test_voicenote_error_has_status_code(self):
        """VoiceNoteError는 status_code 속성을 가져야 한다"""
        exc = VoiceNoteError(error_code="ERR_001", message="테스트 오류", status_code=500)
        assert exc.status_code == 500

    def test_voicenote_error_can_be_raised(self):
        """VoiceNoteError는 raise 가능해야 한다"""
        with pytest.raises(VoiceNoteError):
            raise VoiceNoteError(error_code="ERR_001", message="테스트", status_code=500)


class TestAudioProcessingError:
    """AudioProcessingError 테스트"""

    def test_audio_processing_error_is_voicenote_error(self):
        """AudioProcessingError는 VoiceNoteError를 상속해야 한다"""
        assert issubclass(AudioProcessingError, VoiceNoteError)

    def test_audio_processing_error_default_values(self):
        """AudioProcessingError는 기본 error_code와 status_code를 가져야 한다"""
        exc = AudioProcessingError(message="오디오 처리 실패")
        assert exc.error_code == "AUDIO_PROCESSING_ERROR"
        assert exc.status_code == 422
        assert exc.message == "오디오 처리 실패"

    def test_audio_processing_error_custom_values(self):
        """AudioProcessingError는 커스텀 error_code와 status_code를 받을 수 있어야 한다"""
        exc = AudioProcessingError(
            message="커스텀 오디오 오류",
            error_code="CUSTOM_AUDIO_ERR",
            status_code=400,
        )
        assert exc.error_code == "CUSTOM_AUDIO_ERR"
        assert exc.status_code == 400

    def test_audio_processing_error_is_catchable_as_voicenote_error(self):
        """AudioProcessingError는 VoiceNoteError로 잡힐 수 있어야 한다"""
        with pytest.raises(VoiceNoteError):
            raise AudioProcessingError(message="오디오 처리 실패")


class TestStorageError:
    """StorageError 테스트"""

    def test_storage_error_is_voicenote_error(self):
        """StorageError는 VoiceNoteError를 상속해야 한다"""
        assert issubclass(StorageError, VoiceNoteError)

    def test_storage_error_default_values(self):
        """StorageError는 기본 error_code와 status_code를 가져야 한다"""
        exc = StorageError(message="저장소 오류")
        assert exc.error_code == "STORAGE_ERROR"
        assert exc.status_code == 500
        assert exc.message == "저장소 오류"

    def test_storage_error_custom_values(self):
        """StorageError는 커스텀 값을 받을 수 있어야 한다"""
        exc = StorageError(
            message="디스크 가득 참",
            error_code="DISK_FULL",
            status_code=507,
        )
        assert exc.error_code == "DISK_FULL"
        assert exc.status_code == 507

    def test_storage_error_is_catchable_as_voicenote_error(self):
        """StorageError는 VoiceNoteError로 잡힐 수 있어야 한다"""
        with pytest.raises(VoiceNoteError):
            raise StorageError(message="저장소 오류")


class TestPipelineError:
    """PipelineError 테스트"""

    def test_pipeline_error_is_voicenote_error(self):
        """PipelineError는 VoiceNoteError를 상속해야 한다"""
        assert issubclass(PipelineError, VoiceNoteError)

    def test_pipeline_error_default_values(self):
        """PipelineError는 기본 error_code와 status_code를 가져야 한다"""
        exc = PipelineError(message="파이프라인 오류")
        assert exc.error_code == "PIPELINE_ERROR"
        assert exc.status_code == 500
        assert exc.message == "파이프라인 오류"

    def test_pipeline_error_custom_values(self):
        """PipelineError는 커스텀 값을 받을 수 있어야 한다"""
        exc = PipelineError(
            message="작업 처리 실패",
            error_code="TASK_FAILED",
            status_code=503,
        )
        assert exc.error_code == "TASK_FAILED"
        assert exc.status_code == 503

    def test_pipeline_error_is_catchable_as_voicenote_error(self):
        """PipelineError는 VoiceNoteError로 잡힐 수 있어야 한다"""
        with pytest.raises(VoiceNoteError):
            raise PipelineError(message="파이프라인 오류")

    def test_all_domain_errors_catchable_together(self):
        """모든 도메인 예외를 VoiceNoteError 하나로 처리할 수 있어야 한다"""
        errors = [
            AudioProcessingError(message="오디오 오류"),
            StorageError(message="저장소 오류"),
            PipelineError(message="파이프라인 오류"),
        ]
        for err in errors:
            with pytest.raises(VoiceNoteError):
                raise err
