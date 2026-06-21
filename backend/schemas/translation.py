"""Translation schemas for minutes and summary artifacts."""

from enum import StrEnum

from pydantic import BaseModel, Field


class TranslationSourceType(StrEnum):
    """Supported source artifact types for translation."""

    AUTO = "auto"
    MINUTES = "minutes"
    SUMMARY = "summary"


class TranslationCreateRequest(BaseModel):
    """Translation generation request."""

    target_language: str = Field(..., min_length=2, max_length=32)
    source_language: str | None = Field(default=None, min_length=2, max_length=32)
    source_type: TranslationSourceType = Field(default=TranslationSourceType.AUTO)
    max_tokens: int = Field(default=2400, ge=512, le=4096)
    force_refresh: bool = Field(default=False)


class TranslationResponse(BaseModel):
    """Generated or cached translation response."""

    task_id: str = Field(..., min_length=1)
    source_type: TranslationSourceType
    source_language: str | None = None
    target_language: str = Field(..., min_length=2)
    translated_text: str = Field(..., min_length=1)
    source_excerpt: str = Field(default="")
    cached: bool = Field(default=False)
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
