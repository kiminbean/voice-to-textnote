"""
SPEC-MOBILE-001: FCM 디바이스 등록 Pydantic 스키마

REQ-MOBILE-001: DeviceRegisterRequest - FCM 토큰 등록
REQ-MOBILE-002: DeviceResponse - 디바이스 정보 응답
REQ-MOBILE-003: DeviceListResponse - 디바이스 목록 응답
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    """
    REQ-MOBILE-001: FCM 디바이스 등록 요청

    - fcm_token: Firebase Cloud Messaging 등록 토큰
    - platform: 디바이스 플랫폼 (ios/android)
    - device_id: (선택) 디바이스 고유 식별자
    """

    fcm_token: str = Field(..., min_length=1, description="FCM 등록 토큰")
    platform: Literal["ios", "android"] = Field(..., description="디바이스 플랫폼")
    device_id: str | None = Field(None, description="디바이스 고유 식별자 (선택)")


class DeviceResponse(BaseModel):
    """
    REQ-MOBILE-002: 디바이스 정보 응답

    - id: 디바이스 UUID
    - fcm_token: FCM 등록 토큰 (마스킹 가능)
    - platform: 디바이스 플랫폼
    - device_id: 디바이스 고유 식별자
    - created_at: 등록 일시
    - updated_at: 마지막 갱신 일시
    """

    id: UUID = Field(..., description="디바이스 UUID")
    fcm_token: str = Field(..., description="FCM 등록 토큰")
    platform: Literal["ios", "android"] = Field(..., description="디바이스 플랫폼")
    device_id: str | None = Field(None, description="디바이스 고유 식별자")
    created_at: datetime = Field(..., description="등록 일시")
    updated_at: datetime = Field(..., description="마지막 갱신 일시")


class DeviceListResponse(BaseModel):
    """
    REQ-MOBILE-003: 디바이스 목록 응답

    - devices: 디바이스 정보 리스트
    - total: 총 디바이스 수
    """

    devices: list[DeviceResponse] = Field(default_factory=list, description="디바이스 리스트")
    total: int = Field(..., ge=0, description="총 디바이스 수")
