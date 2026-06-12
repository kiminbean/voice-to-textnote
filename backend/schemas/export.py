"""
내보내기 API 스키마
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExportFormat(str, Enum):
    """내보내기 형식"""
    pdf = "pdf"
    docx = "docx"


class ExportFilter(BaseModel):
    """내보내기 필터"""

    # 날짜 필터
    date_from: datetime | None = Field(None, description="시작 날짜")
    date_to: datetime | None = Field(None, description="종료 날짜")

    # 작업 유형 필터
    task_types: list[str] | None = Field(
        default=None,
        description="내보낼 작업 유형 목록"
    )

    # 화자 필터
    speakers: list[str] | None = Field(
        default=None,
        description="내보낼 화자 목록"
    )

    # 키워드 필터
    keywords: list[str] | None = Field(
        default=None,
        description="내보낼 키워드 목록"
    )


class ExportErrorResponse(BaseModel):
    """내보내기 오류 응답"""

    detail: str = Field(..., description="오류 상세 메시지")


class ExportRequest(BaseModel):
    """내보내기 요청"""

    task_ids: list[str] = Field(
        ...,
        description="내보낼 회의록 ID 목록",
        min_length=1,
        max_length=50
    )

    format: ExportFormat = Field(
        default=ExportFormat.pdf,
        description="내보내기 형식"
    )

    filters: ExportFilter | None = Field(
        default=None,
        description="내보내기 필터 조건"
    )

    include_summary: bool = Field(
        default=True,
        description="요약 내용 포함 여부"
    )

    include_action_items: bool = Field(
        default=True,
        description="액션 아이템 포함 여부"
    )

    include_audio_analysis: bool = Field(
        default=False,
        description="오디오 분석 포함 여부"
    )


class ExportFile(BaseModel):
    """내보내기 파일 정보"""

    task_id: str = Field(..., description="회의록 ID")
    filename: str = Field(..., description="파일명")
    path: str = Field(..., description="파일 경로")
    size_bytes: int = Field(..., description="파일 크기 (바이트)")
    media_type: str = Field(..., description="MIME 타입")
    created_at: datetime = Field(..., description="생성 시간")
    format: ExportFormat = Field(..., description="내보내기 형식")

    # 메타 정보
    title: str | None = Field(None, description="문서 제목")
    page_count: int | None = Field(None, description="페이지 수")
    word_count: int | None = Field(None, description="단어 수")


class ExportResponse(BaseModel):
    """내보내기 응답"""

    request_id: str = Field(..., description="요청 ID")
    total_requested: int = Field(..., description="총 요청 개수")
    total_success: int = Field(..., description="성공한 개수")
    total_failed: int = Field(..., description="실패한 개수")
    export_files: list[ExportFile] = Field(..., description="생성된 파일 목록")
    created_at: datetime = Field(..., description="요청 시간")

    # 오류 정보
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        description="오류 정보 목록"
    )

    # 처리 시간
    processing_time_ms: float | None = Field(
        None,
        description="총 처리 시간 (ms)"
    )


class ExportTemplate(BaseModel):
    """내보내기 템플릿"""

    id: str = Field(..., description="템플릿 ID")
    name: str = Field(..., description="템플릿 이름")
    description: str = Field(..., description="템플릿 설명")
    format: ExportFormat = Field(..., description="대상 형식")

    # 템플릿 구성
    sections: list[str] = Field(..., description="포함된 섹션 목록")
    styling: dict[str, Any] = Field(default_factory=dict, description="스타일 정보")

    # 메타 정보
    is_default: bool = Field(default=False, description="기본 템플릿 여부")
    created_at: datetime = Field(..., description="생성 시간")


class ExportOptions(BaseModel):
    """내보내기 옵션"""

    # 페이지 설정
    page_size: str = Field(default="A4", description="페이지 크기")
    orientation: str = Field(default="portrait", description="페이지 방향")
    margins: dict[str, float] = Field(
        default={"top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54},
        description="페이지 여백 (cm)"
    )

    # 글꼴 설정
    font_family: str = Field(default="NanumGothic", description="글꼴")
    font_size: int = Field(default=11, description="기본 글꼴 크기")

    # 색상 설정
    header_color: str = Field(default="#2563eb", description="헤더 색상")
    text_color: str = Field(default="#1f2937", description="기본 텍스트 색상")

    # 레이아웃 설정
    section_spacing: int = Field(default=12, description="섹션 간격")
    paragraph_spacing: int = Field(default=6, description="단락 간격")
