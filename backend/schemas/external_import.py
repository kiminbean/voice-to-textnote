"""External URL/text import schemas."""

from enum import StrEnum

from pydantic import AnyHttpUrl, BaseModel, Field


class ExternalImportSourceType(StrEnum):
    """Supported external import source categories."""

    WEB = "web"
    YOUTUBE = "youtube"
    VIDEO = "video"
    PODCAST = "podcast"
    DOCUMENT = "document"
    OTHER = "other"


class ExternalTextImportRequest(BaseModel):
    """User-provided transcript/text import request."""

    source_url: AnyHttpUrl = Field(description="원본 외부 URL")
    title: str = Field(min_length=1, max_length=200, description="가져올 노트 제목")
    content: str = Field(
        min_length=20, max_length=200_000, description="사용자가 보유한 원문/Transcript"
    )
    source_type: ExternalImportSourceType = Field(
        default=ExternalImportSourceType.WEB,
        description="외부 소스 유형",
    )
    language: str = Field(default="ko", min_length=2, max_length=16, description="콘텐츠 언어")


class ExternalTextImportResponse(BaseModel):
    """Created imported minutes-compatible result."""

    task_id: str
    status: str
    title: str
    source_url: str
    source_type: ExternalImportSourceType
    language: str
    result_url: str
    search_indexed: bool
    shared_team_ids: list[str] = Field(default_factory=list)


class DocumentImportResponse(ExternalTextImportResponse):
    """Imported document result with extraction metadata."""

    file_name: str
    file_type: str
    extracted_characters: int
