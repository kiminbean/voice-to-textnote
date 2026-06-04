"""
SPEC-MOBILE-001: FCM 디바이스 등록 API 엔드포인트

REQ-MOBILE-001: POST /api/v1/devices/register - FCM 토큰 등록
REQ-MOBILE-002: DELETE /api/v1/devices/{device_id} - 디바이스 등록 해제
REQ-MOBILE-003: GET /api/v1/devices/ - 등록된 디바이스 목록 조회

인증 필요 엔드포인트:
- 모든 엔드포인트는 Bearer JWT 토큰 필요
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.app.errors import not_found
from backend.schemas.device import (
    DeviceListResponse,
    DeviceRegisterRequest,
    DeviceResponse,
)
from backend.services.push_service import get_push_service
from backend.utils.logger import get_logger

router = APIRouter(prefix="/devices", tags=["devices"])
logger = get_logger(__name__)

# PushService 싱글톤
_push_service = get_push_service()


@router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="FCM 디바이스 등록",
)
async def register_device(
    req: DeviceRegisterRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    REQ-MOBILE-001: FCM 토큰을 등록합니다.

    - **fcm_token**: Firebase Cloud Messaging 등록 토큰
    - **platform**: 디바이스 플랫폼 (ios/android)
    - **device_id**: (선택) 디바이스 고유 식별자

    MVP: 인메모리 저장, 실제 DB 저장 없음
    """
    # 디바이스 ID 생성 (UUID v4)
    device_id_uuid = str(uuid.uuid4())

    # MVP: device_id 필드가 없으면 UUID 사용
    device_identifier = req.device_id or device_id_uuid

    # PushService에 등록 (인메모리)
    _push_service.register_device(device_identifier, req.fcm_token)

    # 응답 생성
    now = datetime.now(UTC)

    logger.info(
        f"디바이스 등록: user_id={current_user.id}, "
        f"device_id={device_identifier}, platform={req.platform}"
    )

    return DeviceResponse(
        id=uuid.UUID(device_id_uuid),
        fcm_token=req.fcm_token,
        platform=req.platform,
        device_id=req.device_id,
        created_at=now,
        updated_at=now,
    )


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="FCM 디바이스 등록 해제",
)
async def unregister_device(
    device_id: str,
    current_user=Depends(get_current_user),
) -> None:
    """
    REQ-MOBILE-002: FCM 토큰 등록을 해제합니다.

    - **device_id**: 디바이스 고유 식별자
    """
    # PushService에서 해제
    deleted = _push_service.unregister_device(device_id)

    if not deleted:
        not_found(f"디바이스를 찾을 수 없습니다: device_id={device_id}")

    logger.info(f"디바이스 해제: user_id={current_user.id}, device_id={device_id}")


@router.get(
    "/",
    response_model=DeviceListResponse,
    summary="등록된 디바이스 목록 조회",
)
async def list_devices(
    current_user=Depends(get_current_user),
) -> DeviceListResponse:
    """
    REQ-MOBILE-003: 현재 사용자의 등록된 모든 디바이스를 반환합니다.

    MVP: 인메모리 저장소에서 조회
    """
    # PushService에서 모든 디바이스 조회
    devices_dict = _push_service.get_all_devices()

    # DeviceResponse 리스트로 변환
    devices = []
    for device_id, fcm_token in devices_dict.items():
        devices.append(
            DeviceResponse(
                id=uuid.UUID(device_id) if is_valid_uuid(device_id) else uuid.uuid4(),
                fcm_token=fcm_token,
                platform="ios",  # MVP: 고정값 (프로덕션: DB에서 조회)
                device_id=device_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    logger.info(f"디바이스 목록 조회: user_id={current_user.id}, count={len(devices)}")

    return DeviceListResponse(devices=devices, total=len(devices))


def is_valid_uuid(uuid_str: str) -> bool:
    """UUID 문자열 유효성 검사"""
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False
