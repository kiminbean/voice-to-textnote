"""
회의록 양식 요청/응답 Pydantic v2 스키마
REQ-TMPL-001: 양식 업로드 응답
REQ-TMPL-003: 양식 목록/상세/삭제 응답
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TemplateUploadResponse(BaseModel):
    """POST /api/v1/templates 응답 (REQ-TMPL-001)"""

    # 양식 고유 ID
    template_id: str = Field(..., description="양식 고유 ID")
    # 양식 이름
    name: str = Field(..., description="양식 이름")
    # 파일 형식 (docx, pdf)
    format: str = Field(..., description="파일 형식 (docx/pdf)")
    # 파싱된 구조
    structure: dict = Field(..., description="양식 구조 (섹션, 필드, 테이블 여부)")
    # 생성 시각
    created_at: str = Field(..., description="업로드 시각 (ISO 8601)")


class TemplateListItem(BaseModel):
    """GET /api/v1/templates 목록 항목 (REQ-TMPL-003)"""

    # 양식 고유 ID
    template_id: str = Field(..., description="양식 고유 ID")
    # 양식 이름
    name: str = Field(..., description="양식 이름")
    # 파일 형식
    format: str = Field(..., description="파일 형식 (docx/pdf)")
    # 생성 시각
    created_at: str = Field(..., description="업로드 시각 (ISO 8601)")


class TemplateDetail(BaseModel):
    """GET /api/v1/templates/{template_id} 상세 응답 (REQ-TMPL-003)"""

    # 양식 고유 ID
    template_id: str = Field(..., description="양식 고유 ID")
    # 양식 이름
    name: str = Field(..., description="양식 이름")
    # 파일 형식
    format: str = Field(..., description="파일 형식 (docx/pdf)")
    # 파싱된 구조
    structure: dict = Field(..., description="양식 구조 (섹션, 필드, 테이블 여부)")
    # 생성 시각
    created_at: str = Field(..., description="업로드 시각 (ISO 8601)")
