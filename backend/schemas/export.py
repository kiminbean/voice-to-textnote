"""
SPEC-EXPORT-001: PDF 내보내기 요청/응답 Pydantic v2 스키마
"""

from pydantic import BaseModel, Field


class ExportErrorResponse(BaseModel):
    """
    PDF 내보내기 오류 응답 스키마

    404, 422, 500 오류 시 반환되는 응답 형식
    """

    # 오류 상세 메시지
    detail: str = Field(..., description="오류 상세 내용")
