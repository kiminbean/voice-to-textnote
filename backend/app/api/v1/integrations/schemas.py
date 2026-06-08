"""
외부 서비스 통합 API 관련 Pydantic 스키마
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class IntegrationType(str, Enum):
    """통합 서비스 타입"""
    SLACK = "slack"
    TEAMS = "teams"
    NOTION = "notion"
    DISCORD = "discord"
    ZOOM = "zoom"


class IntegrationStatus(str, Enum):
    """통합 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    TESTING = "testing"


class SlackConfig(BaseModel):
    """Slack 통합 설정"""
    webhook_url: str = Field(..., description="Slack 웹훅 URL")
    channel: str = Field(..., description="채널 이름")
    username: str | None = Field(None, description="봇 이름")
    icon_emoji: str | None = Field(None, description="아이콘 이모지")

    @validator('webhook_url')
    def validate_webhook_url(cls, v):  # noqa: N805
        if not v.startswith('https://hooks.slack.com/'):
            raise ValueError('유효한 Slack 웹훅 URL이 아닙니다')
        return v


class TeamsConfig(BaseModel):
    """Microsoft Teams 통합 설정"""
    webhook_url: str = Field(..., description="Teams 웹훅 URL")
    theme_color: str | None = Field(None, description="테마 색상")

    @validator('webhook_url')
    def validate_webhook_url(cls, v):  # noqa: N805
        if not v.startswith('https://'):
            raise ValueError('유효한 웹훅 URL이 아닙니다')
        return v


class NotionConfig(BaseModel):
    """Notion 통합 설정"""
    integration_token: str = Field(..., description="Notion 통합 토큰")
    database_id: str = Field(..., description="데이터베이스 ID")
    page_title_template: str = Field("회의록: {meeting_title}", description="페이지 제목 템플릿")

    @validator('integration_token')
    def validate_token(cls, v):  # noqa: N805
        if len(v) < 10:
            raise ValueError('유효한 Notion 토큰이 아닙니다')
        return v


class DiscordConfig(BaseModel):
    """Discord 통합 설정"""
    webhook_url: str = Field(..., description="Discord 웹훅 URL")
    username: str | None = Field(None, description="봇 이름")
    avatar_url: str | None = Field(None, description="아바타 URL")

    @validator('webhook_url')
    def validate_webhook_url(cls, v):  # noqa: N805
        if not v.startswith('https://discord.com/api/webhooks/'):
            raise ValueError('유효한 Discord 웹훅 URL이 아닙니다')
        return v


class WebhookConfig(BaseModel):
    """일반 웹훅 설정"""
    url: str = Field(..., description="웹훅 URL")
    headers: dict[str, str] = Field(default_factory=dict, description="추가 헤더")
    timeout: int = Field(30, ge=1, le=300, description="타임아웃 (초)")
    retry_count: int = Field(3, ge=0, le=10, description="재시도 횟수")


class IntegrationRequest(BaseModel):
    """통합 생성 요청"""
    integration_type: IntegrationType = Field(..., description="통합 타입")
    config: dict[str, Any] = Field(..., description="통합 설정")

    @validator('config')
    def validate_config(cls, v, values):  # noqa: N805
        integration_type = values.get('integration_type')
        if integration_type == IntegrationType.SLACK:
            return SlackConfig(**v).dict()
        elif integration_type == IntegrationType.TEAMS:
            return TeamsConfig(**v).dict()
        elif integration_type == IntegrationType.NOTION:
            return NotionConfig(**v).dict()
        elif integration_type == IntegrationType.DISCORD:
            return DiscordConfig(**v).dict()
        else:
            return v


class IntegrationResponse(BaseModel):
    """통합 응답"""
    integration_id: str = Field(..., description="통합 ID")
    integration_type: IntegrationType = Field(..., description="통합 타입")
    status: IntegrationStatus = Field(..., description="상태")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: datetime | None = Field(None, description="업데이트 시간")
    config: dict[str, Any] = Field(..., description="통합 설정")
    last_sync_at: datetime | None = Field(None, description="마지막 동기화 시간")


class WebhookResponse(BaseModel):
    """웹훅 응답"""
    status: str = Field(..., description="처리 상태")
    message: str = Field(..., description="메시지")
    data: dict[str, Any] | None = Field(None, description="데이터")
    timestamp: datetime = Field(..., description="타임스탬프")


class SyncStatus(BaseModel):
    """동기화 상태"""
    integration_id: str = Field(..., description="통합 ID")
    last_sync: datetime | None = Field(None, description="마지막 동기화 시간")
    sync_count: int = Field(0, description="동기화 횟수")
    error_count: int = Field(0, description="오류 횟수")
    is_active: bool = Field(True, description="활성 상태")


class MeetingExportData(BaseModel):
    """회의록 내보내기 데이터"""
    meeting_id: str = Field(..., description="회의 ID")
    title: str = Field(..., description="회의 제목")
    duration: float = Field(..., description="회의 시간 (분)")
    participants: list[str] = Field(..., description="참가자 목록")
    summary: str = Field(..., description="회의 요약")
    key_points: list[str] = Field(..., description="주요 내용")
    action_items: list[dict] = Field(..., description="실행 항목")
    full_transcript: str = Field(..., description="전체 회의록")


class SyncTrigger(BaseModel):
    """동기화 트리거"""
    event_type: str = Field(..., description="이벤트 타입")
    meeting_id: str = Field(..., description="회의 ID")
    data: dict[str, Any] = Field(..., description="데이터")
