"""
PDF 내보내기 스키마 테스트
SPEC-EXPORT-001: ExportErrorResponse 스키마 검증
"""

import pytest
from pydantic import ValidationError

from backend.schemas.export import ExportErrorResponse


class TestExportErrorResponse:
    """ExportErrorResponse 스키마 테스트"""

    def test_export_error_response_valid_input(self):
        """유효한 오류 메시지로 ExportErrorResponse 생성 성공"""
        # Arrange & Act
        response = ExportErrorResponse(detail="Meeting not found")

        # Assert
        assert response.detail == "Meeting not found"

    def test_export_error_response_empty_string(self):
        """빈 문자열도 허용되는지 확인 (required지만 빈 문자열은 유효)"""
        # Arrange & Act
        response = ExportErrorResponse(detail="")

        # Assert
        assert response.detail == ""

    def test_export_error_response_long_message(self):
        """긴 오류 메시지 처리 확인"""
        # Arrange
        long_message = "Error occurred while processing export request: " * 10

        # Act
        response = ExportErrorResponse(detail=long_message)

        # Assert
        assert len(response.detail) > 0
        assert "Error occurred while processing export request:" in response.detail

    def test_export_error_response_missing_detail(self):
        """detail 필드가 없으면 ValidationError 발생"""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            ExportErrorResponse()

        # ValidationError 메시지 확인
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("detail",) for error in errors)
        assert any(error["type"] == "missing" for error in errors)

    def test_export_error_response_json_serialization(self):
        """JSON 직렬화가 올바르게 동작하는지 확인"""
        # Arrange
        response = ExportErrorResponse(detail="Invalid export format")

        # Act
        json_data = response.model_dump()

        # Assert
        assert json_data == {"detail": "Invalid export format"}

    def test_export_error_response_from_dict(self):
        """dict에서 ExportErrorResponse 생성 성공"""
        # Arrange
        data = {"detail": "Export failed due to server error"}

        # Act
        response = ExportErrorResponse(**data)

        # Assert
        assert response.detail == "Export failed due to server error"

    def test_export_error_response_with_special_characters(self):
        """특수 문자가 포함된 메시지 처리 확인"""
        # Arrange & Act
        response = ExportErrorResponse(detail="Error: 'PDF generation failed' at line 42")

        # Assert
        assert "PDF generation failed" in response.detail
        assert "line 42" in response.detail

    def test_export_error_response_unicode(self):
        """유니코드 문자(한글) 처리 확인"""
        # Arrange & Act
        response = ExportErrorResponse(detail="회의를 찾을 수 없습니다")

        # Assert
        assert response.detail == "회의를 찾을 수 없습니다"
