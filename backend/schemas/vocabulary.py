"""
REQ-VOCAB-001: 커스텀 어휘 Pydantic v2 스키마
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VocabularyCreate(BaseModel):
    """POST /api/v1/vocabulary 요청 바디"""

    name: str = Field(..., min_length=1, max_length=100, description="어휘 리스트 이름")
    words: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="용어 목록 (최대 500개)",
    )


class VocabularyUpdate(BaseModel):
    """PUT /api/v1/vocabulary/{vocab_id} 요청 바디"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    words: list[str] | None = Field(default=None, min_length=1, max_length=500)


class VocabularyResponse(BaseModel):
    """어휘 리스트 응답"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    words: list[str]
    created_at: datetime
    updated_at: datetime


class VocabularyListResponse(BaseModel):
    """어휘 목록 응답"""

    items: list[VocabularyResponse]
    total: int
