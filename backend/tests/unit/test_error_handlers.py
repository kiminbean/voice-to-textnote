"""
REQ-ERR-003 ~ REQ-ERR-006: 전역 예외 핸들러 테스트
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.error_handlers import register_exception_handlers
from backend.app.exceptions import (
    AudioProcessingError,
    PipelineError,
    StorageError,
    VoiceNoteError,
)


def create_test_app() -> FastAPI:
    """테스트용 FastAPI 앱 생성"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test/voicenote-error")
    async def trigger_voicenote_error():
        raise VoiceNoteError(
            error_code="TEST_ERROR",
            message="테스트 VoiceNote 오류",
            status_code=400,
        )

    @app.get("/test/audio-error")
    async def trigger_audio_error():
        raise AudioProcessingError(message="오디오 처리 실패")

    @app.get("/test/storage-error")
    async def trigger_storage_error():
        raise StorageError(message="저장소 접근 실패")

    @app.get("/test/pipeline-error")
    async def trigger_pipeline_error():
        raise PipelineError(message="파이프라인 실패")

    @app.get("/test/unhandled-error")
    async def trigger_unhandled_error():
        raise RuntimeError("예기치 않은 오류")

    @app.post("/test/validation-error")
    async def trigger_validation_error(body: dict):
        pass

    return app


@pytest.fixture
def client():
    """테스트 클라이언트 픽스처"""
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


class TestVoiceNoteErrorHandler:
    """VoiceNoteError 핸들러 테스트 (REQ-ERR-003, REQ-ERR-004)"""

    def test_voicenote_error_returns_error_code(self, client):
        """VoiceNoteError 응답에 error_code 포함 (REQ-ERR-004)"""
        response = client.get("/test/voicenote-error")
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "TEST_ERROR"

    def test_voicenote_error_returns_message(self, client):
        """VoiceNoteError 응답에 message 포함 (REQ-ERR-004)"""
        response = client.get("/test/voicenote-error")
        data = response.json()
        assert "message" in data
        assert data["message"] == "테스트 VoiceNote 오류"

    def test_voicenote_error_returns_request_id(self, client):
        """VoiceNoteError 응답에 request_id 포함 (REQ-ERR-004)"""
        response = client.get("/test/voicenote-error")
        data = response.json()
        assert "request_id" in data

    def test_voicenote_error_correct_status_code(self, client):
        """VoiceNoteError는 지정된 HTTP 상태 코드를 반환해야 한다"""
        response = client.get("/test/voicenote-error")
        assert response.status_code == 400

    def test_voicenote_error_no_extra_fields(self, client):
        """에러 응답에 불필요한 필드 없음 - 정확히 3개 필드만 포함"""
        response = client.get("/test/voicenote-error")
        data = response.json()
        assert set(data.keys()) == {"error_code", "message", "request_id"}


class TestAudioProcessingErrorHandler:
    """AudioProcessingError 핸들러 테스트"""

    def test_audio_error_correct_status_code(self, client):
        """AudioProcessingError는 422 상태 코드를 반환해야 한다"""
        response = client.get("/test/audio-error")
        assert response.status_code == 422

    def test_audio_error_correct_error_code(self, client):
        """AudioProcessingError 응답의 error_code 확인"""
        response = client.get("/test/audio-error")
        data = response.json()
        assert data["error_code"] == "AUDIO_PROCESSING_ERROR"

    def test_audio_error_correct_message(self, client):
        """AudioProcessingError 응답의 message 확인"""
        response = client.get("/test/audio-error")
        data = response.json()
        assert data["message"] == "오디오 처리 실패"


class TestStorageErrorHandler:
    """StorageError 핸들러 테스트"""

    def test_storage_error_correct_status_code(self, client):
        """StorageError는 500 상태 코드를 반환해야 한다"""
        response = client.get("/test/storage-error")
        assert response.status_code == 500

    def test_storage_error_correct_error_code(self, client):
        """StorageError 응답의 error_code 확인"""
        response = client.get("/test/storage-error")
        data = response.json()
        assert data["error_code"] == "STORAGE_ERROR"


class TestPipelineErrorHandler:
    """PipelineError 핸들러 테스트"""

    def test_pipeline_error_correct_status_code(self, client):
        """PipelineError는 500 상태 코드를 반환해야 한다"""
        response = client.get("/test/pipeline-error")
        assert response.status_code == 500

    def test_pipeline_error_correct_error_code(self, client):
        """PipelineError 응답의 error_code 확인"""
        response = client.get("/test/pipeline-error")
        data = response.json()
        assert data["error_code"] == "PIPELINE_ERROR"


class TestUnhandledExceptionHandler:
    """처리되지 않은 예외 핸들러 테스트 (REQ-ERR-003, REQ-ERR-005)"""

    def test_unhandled_error_returns_500(self, client):
        """처리되지 않은 예외는 500 상태 코드를 반환해야 한다"""
        response = client.get("/test/unhandled-error")
        assert response.status_code == 500

    def test_unhandled_error_returns_consistent_format(self, client):
        """처리되지 않은 예외도 일관된 JSON 형식을 반환해야 한다 (REQ-ERR-003)"""
        response = client.get("/test/unhandled-error")
        data = response.json()
        assert "error_code" in data
        assert "message" in data
        assert "request_id" in data

    def test_unhandled_error_no_stack_trace(self, client):
        """프로덕션 환경에서 스택 트레이스를 클라이언트에 노출하지 않아야 한다 (REQ-ERR-005)"""
        response = client.get("/test/unhandled-error")
        data = response.json()
        # 스택 트레이스 관련 키가 없어야 함
        assert "traceback" not in data
        assert "detail" not in data
        assert "stack_trace" not in data

    def test_unhandled_error_generic_message(self, client):
        """처리되지 않은 예외는 내부 오류 메시지를 노출하지 않아야 한다 (REQ-ERR-005)"""
        response = client.get("/test/unhandled-error")
        data = response.json()
        # 내부 RuntimeError 메시지("예기치 않은 오류")가 노출되면 안 됨
        assert "예기치 않은 오류" not in data.get("message", "")
        assert "RuntimeError" not in data.get("message", "")

    def test_unhandled_error_code(self, client):
        """처리되지 않은 예외의 error_code 확인"""
        response = client.get("/test/unhandled-error")
        data = response.json()
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"


class TestRequestValidationErrorHandler:
    """RequestValidationError 핸들러 테스트 (REQ-ERR-006)"""

    def test_validation_error_returns_422(self, client):
        """잘못된 요청은 422 상태 코드를 반환해야 한다 (REQ-ERR-006)"""
        # JSON body 없이 POST 요청 → 422 ValidationError 유발
        response = client.post("/test/validation-error", content="invalid json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422

    def test_validation_error_returns_error_code(self, client):
        """검증 오류 응답에 error_code 포함 (REQ-ERR-006)"""
        response = client.post("/test/validation-error", content="invalid json", headers={"Content-Type": "application/json"})
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"

    def test_validation_error_returns_field_details(self, client):
        """검증 오류 응답에 필드별 오류 상세 포함 (REQ-ERR-006)"""
        response = client.post("/test/validation-error", content="invalid json", headers={"Content-Type": "application/json"})
        data = response.json()
        # 필드 레벨 오류 상세가 포함되어야 함
        assert "details" in data

    def test_validation_error_has_request_id(self, client):
        """검증 오류 응답에 request_id 포함"""
        response = client.post("/test/validation-error", content="invalid json", headers={"Content-Type": "application/json"})
        data = response.json()
        assert "request_id" in data
