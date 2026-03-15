"""
Pydantic 스키마 검증 단위 테스트
REQ-STT-001, REQ-STT-008, REQ-STT-010, REQ-STT-011
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# SegmentResult 스키마 테스트
# ---------------------------------------------------------------------------

class TestSegmentResult:
    """전사 세그먼트 결과 스키마 검증 (REQ-STT-008)"""

    def test_valid_segment_accepted(self):
        """올바른 세그먼트 데이터 통과"""
        from backend.schemas.transcription import SegmentResult

        segment = SegmentResult(id=0, start=0.0, end=4.2, text="안녕하세요.", confidence=0.95)
        assert segment.id == 0
        assert segment.start == 0.0
        assert segment.end == 4.2
        assert segment.text == "안녕하세요."
        assert segment.confidence == pytest.approx(0.95)

    def test_confidence_range_valid(self):
        """confidence는 0.0~1.0 범위"""
        from backend.schemas.transcription import SegmentResult

        seg_min = SegmentResult(id=0, start=0.0, end=1.0, text="ok", confidence=0.0)
        assert seg_min.confidence == 0.0

        seg_max = SegmentResult(id=0, start=0.0, end=1.0, text="ok", confidence=1.0)
        assert seg_max.confidence == 1.0

    def test_confidence_above_1_rejected(self):
        """confidence > 1.0 → ValidationError"""
        from backend.schemas.transcription import SegmentResult

        with pytest.raises(ValidationError):
            SegmentResult(id=0, start=0.0, end=1.0, text="bad", confidence=1.5)

    def test_confidence_below_0_rejected(self):
        """confidence < 0.0 → ValidationError"""
        from backend.schemas.transcription import SegmentResult

        with pytest.raises(ValidationError):
            SegmentResult(id=0, start=0.0, end=1.0, text="bad", confidence=-0.1)

    def test_confidence_defaults_to_zero(self):
        """confidence 미지정 시 기본값 0.0"""
        from backend.schemas.transcription import SegmentResult

        segment = SegmentResult(id=0, start=0.0, end=1.0, text="텍스트")
        assert segment.confidence == 0.0

    def test_frozen_model_immutable(self):
        """frozen=True: 속성 변경 불가"""
        from backend.schemas.transcription import SegmentResult

        segment = SegmentResult(id=0, start=0.0, end=1.0, text="텍스트")
        with pytest.raises(Exception):  # ValidationError 또는 AttributeError
            segment.text = "변경 불가"

    def test_segment_serialization(self):
        """model_dump() 직렬화 결과 확인"""
        from backend.schemas.transcription import SegmentResult

        seg = SegmentResult(id=1, start=2.5, end=5.0, text="테스트", confidence=0.9)
        data = seg.model_dump()
        assert data["id"] == 1
        assert data["start"] == 2.5
        assert data["end"] == 5.0
        assert data["text"] == "테스트"
        assert data["confidence"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# TaskStatus 열거형 테스트
# ---------------------------------------------------------------------------

class TestTaskStatus:
    """작업 상태 열거형 테스트 (REQ-STT-010)"""

    def test_all_status_values_exist(self):
        """pending, processing, completed, failed 상태 모두 존재"""
        from backend.schemas.transcription import TaskStatus

        assert TaskStatus.pending is not None
        assert TaskStatus.processing is not None
        assert TaskStatus.completed is not None
        assert TaskStatus.failed is not None

    def test_status_string_values_lowercase(self):
        """상태값은 소문자 문자열 (API 응답 일관성)"""
        from backend.schemas.transcription import TaskStatus

        assert TaskStatus.pending.value == "pending"
        assert TaskStatus.processing.value == "processing"
        assert TaskStatus.completed.value == "completed"
        assert TaskStatus.failed.value == "failed"

    def test_status_from_string_value(self):
        """문자열에서 TaskStatus 생성 가능"""
        from backend.schemas.transcription import TaskStatus

        assert TaskStatus("pending") == TaskStatus.pending
        assert TaskStatus("completed") == TaskStatus.completed

    def test_invalid_status_raises_error(self):
        """정의되지 않은 상태값은 ValueError"""
        from backend.schemas.transcription import TaskStatus

        with pytest.raises(ValueError):
            TaskStatus("unknown_status")


# ---------------------------------------------------------------------------
# TranscriptionCreate (POST 201 응답 스키마) 테스트
# ---------------------------------------------------------------------------

class TestTranscriptionCreate:
    """POST /api/v1/transcriptions 201 응답 스키마"""

    def test_valid_response_schema(self):
        """올바른 응답 스키마 생성"""
        from backend.schemas.transcription import TaskStatus, TranscriptionCreate

        task_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        response = TranscriptionCreate(
            task_id=task_id,
            status=TaskStatus.pending,
            status_url=f"/api/v1/transcriptions/{task_id}/status",
            result_url=f"/api/v1/transcriptions/{task_id}",
            created_at=now,
        )
        assert response.task_id == task_id
        assert response.status == TaskStatus.pending
        assert "/status" in response.status_url
        assert str(task_id) in response.result_url

    def test_response_serialization(self):
        """응답이 올바르게 직렬화됨 (시나리오 1: task_id, status_url, result_url 포함)"""
        from backend.schemas.transcription import TaskStatus, TranscriptionCreate

        task_id = uuid.uuid4()
        response = TranscriptionCreate(
            task_id=task_id,
            status=TaskStatus.pending,
            status_url="/api/v1/transcriptions/abc/status",
            result_url="/api/v1/transcriptions/abc",
            created_at=datetime.now(timezone.utc),
        )
        data = response.model_dump()
        assert "task_id" in data
        assert "status" in data
        assert "status_url" in data
        assert "result_url" in data
        assert "created_at" in data


# ---------------------------------------------------------------------------
# TaskStatusResponse 스키마 테스트
# ---------------------------------------------------------------------------

class TestTaskStatusResponse:
    """작업 상태 조회 응답 스키마 (REQ-STT-010, 시나리오 3)"""

    def test_required_fields_present(self):
        """task_id, status, created_at, updated_at 필드 포함 (시나리오 3)"""
        from backend.schemas.transcription import TaskStatus, TaskStatusResponse

        now = datetime.now(timezone.utc)
        response = TaskStatusResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.processing,
            created_at=now,
            updated_at=now,
        )
        data = response.model_dump()
        for field in ("task_id", "status", "created_at", "updated_at"):
            assert field in data, f"상태 응답에 '{field}' 필드 누락"

    def test_failed_status_includes_error_message(self):
        """실패 상태 응답에 error_message 포함 (시나리오 3, 7)"""
        from backend.schemas.transcription import TaskStatus, TaskStatusResponse

        now = datetime.now(timezone.utc)
        response = TaskStatusResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.failed,
            created_at=now,
            updated_at=now,
            error_message="파일 손상: 디코딩 실패",
        )
        data = response.model_dump()
        assert data["error_message"] == "파일 손상: 디코딩 실패"

    def test_progress_defaults_to_zero(self):
        """progress 미지정 시 기본값 0.0"""
        from backend.schemas.transcription import TaskStatus, TaskStatusResponse

        now = datetime.now(timezone.utc)
        response = TaskStatusResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.pending,
            created_at=now,
            updated_at=now,
        )
        assert response.progress == 0.0

    def test_progress_range_valid(self):
        """progress는 0.0~1.0 범위"""
        from backend.schemas.transcription import TaskStatus, TaskStatusResponse

        now = datetime.now(timezone.utc)
        response = TaskStatusResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.processing,
            progress=0.65,
            created_at=now,
            updated_at=now,
        )
        assert response.progress == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# TranscriptionResponse 스키마 테스트
# ---------------------------------------------------------------------------

class TestTranscriptionResponse:
    """전사 결과 응답 스키마 직렬화 테스트 (REQ-STT-011)"""

    def test_response_serialization(self):
        """응답 JSON 직렬화 성공 (시나리오 1)"""
        from backend.schemas.transcription import (
            SegmentResult, TaskStatus, TranscriptionResponse,
        )

        now = datetime.now(timezone.utc)
        response = TranscriptionResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.completed,
            language="ko",
            segments=[
                SegmentResult(id=0, start=0.0, end=4.2, text="안녕", confidence=0.95)
            ],
            duration=4.2,
            created_at=now,
        )
        data = response.model_dump()
        assert data["language"] == "ko"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "안녕"

    def test_response_required_fields(self):
        """응답에 task_id, status, language, segments 필드 포함 (시나리오 1)"""
        from backend.schemas.transcription import (
            SegmentResult, TaskStatus, TranscriptionResponse,
        )

        now = datetime.now(timezone.utc)
        response = TranscriptionResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.completed,
            language="ko",
            segments=[
                SegmentResult(id=0, start=0.0, end=1.0, text="테스트", confidence=0.9)
            ],
            created_at=now,
        )
        data = response.model_dump()
        for field in ("task_id", "status", "language", "segments"):
            assert field in data, f"응답에 '{field}' 필드 누락"

    def test_segments_default_empty_list(self):
        """segments 미지정 시 빈 리스트"""
        from backend.schemas.transcription import TaskStatus, TranscriptionResponse

        response = TranscriptionResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        assert response.segments == []

    def test_duration_field_name(self):
        """재생 시간 필드명이 'duration' (total_duration 아님)"""
        from backend.schemas.transcription import TaskStatus, TranscriptionResponse

        response = TranscriptionResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.completed,
            language="ko",
            duration=1234.5,
            created_at=datetime.now(timezone.utc),
        )
        assert response.duration == 1234.5
        data = response.model_dump()
        assert "duration" in data
        assert "total_duration" not in data

    def test_error_response_has_no_segments(self):
        """실패 응답에서 segments가 비어있음 (REQ-STT-009)"""
        from backend.schemas.transcription import TaskStatus, TranscriptionResponse

        response = TranscriptionResponse(
            task_id=uuid.uuid4(),  # type: ignore[arg-type]
            status=TaskStatus.failed,
            error_message="손상된 파일",
            created_at=datetime.now(timezone.utc),
        )
        assert response.segments == []
        assert response.error_message == "손상된 파일"


# ---------------------------------------------------------------------------
# ValidationErrorDetail/ValidationErrorResponse 스키마 테스트
# ---------------------------------------------------------------------------

class TestValidationErrorResponse:
    """422 응답 스키마 테스트 (시나리오 2, 5)"""

    def test_validation_error_detail_structure(self):
        """ValidationErrorDetail에 field, message, type 포함 (시나리오 2)"""
        from backend.schemas.transcription import ValidationErrorDetail

        detail = ValidationErrorDetail(
            field="file",
            message="지원하지 않는 파일 형식입니다",
            type="unsupported_format",
        )
        assert detail.field == "file"
        assert "지원하지 않는" in detail.message
        assert detail.type == "unsupported_format"

    def test_validation_error_response_contains_detail_list(self):
        """ValidationErrorResponse.detail가 리스트"""
        from backend.schemas.transcription import (
            ValidationErrorDetail, ValidationErrorResponse,
        )

        response = ValidationErrorResponse(detail=[
            ValidationErrorDetail(
                field="file",
                message="파일 크기 초과",
                type="file_too_large",
            )
        ])
        assert isinstance(response.detail, list)
        assert len(response.detail) == 1
