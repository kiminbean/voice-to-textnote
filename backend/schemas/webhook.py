"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 Pydantic 스키마
"""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from backend.db.webhook_models import WEBHOOK_EVENT_TYPES


class WebhookEndpointCreate(BaseModel):
    """웹훅 엔드포인트 생성 요청"""

    url: Annotated[str, AnyHttpUrl] = Field(..., description="수신 URL (HTTP/HTTPS)")
    events: list[str] = Field(
        default_factory=list,
        description="수신할 이벤트 타입. 빈 배열이면 전체 이벤트 수신.",
    )
    secret: str | None = Field(
        default=None,
        max_length=255,
        description="HMAC-SHA256 서명 키. 설정 시 X-Webhook-Signature 헤더 포함.",
    )
    description: str | None = Field(default=None, max_length=500)

    @field_validator("url", mode="before")
    @classmethod
    def coerce_url_to_str(cls, v: object) -> str:
        return str(v)

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        for event in v:
            if event not in WEBHOOK_EVENT_TYPES:
                raise ValueError(
                    f"지원하지 않는 이벤트 타입: {event!r}. "
                    f"지원 목록: {sorted(WEBHOOK_EVENT_TYPES)}"
                )
        return list(dict.fromkeys(v))  # 중복 제거, 순서 유지


class WebhookEndpointUpdate(BaseModel):
    """웹훅 엔드포인트 부분 수정 요청"""

    url: str | None = Field(default=None, max_length=500)
    events: list[str] | None = None
    secret: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for event in v:
            if event not in WEBHOOK_EVENT_TYPES:
                raise ValueError(f"지원하지 않는 이벤트 타입: {event!r}")
        return list(dict.fromkeys(v))


class WebhookEndpointResponse(BaseModel):
    """웹훅 엔드포인트 응답 (secret은 마스킹)"""

    id: uuid.UUID
    user_id: uuid.UUID
    url: str
    events: list[str]
    has_secret: bool
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, obj: object) -> "WebhookEndpointResponse":
        """ORM 객체에서 생성 (secret은 has_secret boolean으로 마스킹)."""
        return cls(
            id=obj.id,  # type: ignore[attr-defined]
            user_id=obj.user_id,  # type: ignore[attr-defined]
            url=obj.url,  # type: ignore[attr-defined]
            events=obj.events or [],  # type: ignore[attr-defined]
            has_secret=obj.secret is not None,  # type: ignore[attr-defined]
            is_active=obj.is_active,  # type: ignore[attr-defined]
            description=obj.description,  # type: ignore[attr-defined]
            created_at=obj.created_at,  # type: ignore[attr-defined]
            updated_at=obj.updated_at,  # type: ignore[attr-defined]
        )


class WebhookEndpointListResponse(BaseModel):
    """웹훅 엔드포인트 목록 응답"""

    items: list[WebhookEndpointResponse]
    total: int


class WebhookPingResponse(BaseModel):
    """웹훅 핑 테스트 응답"""

    webhook_id: uuid.UUID
    url: str
    status_code: int | None
    success: bool
    message: str
