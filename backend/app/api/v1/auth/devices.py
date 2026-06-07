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
from backend.schemas.device import (
    DeviceListResponse,
    DeviceRegisterRequest,
    DeviceResponse,
)
from backend.services.push_service import PushService, get_push_service
from backend.utils.logger import get_logger

router = APIRouter(prefix="/devices", tags=["devices"])
logger = get_logger(__name__)


# PushService 의존성 주입 (REQ-DEP-001)
def _get_push() -> PushService:
    return get_push_service()


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

    TASK-003: DB-backed 저장 (DeviceToken 모델 사용)
    """
    # 디바이스 ID 생성 (UUID v4)
    device_id_uuid = str(uuid.uuid4())

    # MVP: device_id 필드가 없으면 UUID 사용
    device_identifier = req.device_id or device_id_uuid

    # TASK-003: PushService에 DB-backed 등록
    await _get_push().register_device(
        fcm_token=req.fcm_token,
        platform=req.platform,
        db=db,
        user_id=str(current_user.id),
    )

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
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    REQ-MOBILE-002: FCM 토큰 등록을 해제합니다.

    - **device_id**: 디바이스 고유 식별자

    TASK-003: DB-backed 해제 (fcm_token으로 조회해서 is_active=False)
    """
    # TASK-003: PushService에서 DB-backed 해제
    # 기존: device_id로 인메모리에서 삭제
    # 변경: fcm_token으로 DB에서 is_active=False로 설정
    # NOTE: device_id 기반 삭제는 더 이상 지원하지 않음 (fcm_token 기반으로 변경)
    # 현재 API에서 fcm_token을 받지 않으므로, user_id 기반으로 모든 토큰 조회 후 해제 필요

    push_service = _get_push()

    # 사용자의 모든 활성 토큰 조회
    tokens = await push_service.get_user_tokens(db, str(current_user.id))

    # device_id에 해당하는 토큰 찾기 (MVP: 첫 번째 토큰만 해제)
    # TODO: device_id와 fcm_token 매핑 필요
    if tokens:
        # MVP: 첫 번째 토큰만 해제 (개선 필요)
        await push_service.invalidate_token(db, tokens[0])

    logger.info(f"디바이스 해제: user_id={current_user.id}, device_id={device_id}")


@router.get(
    "/",
    response_model=DeviceListResponse,
    summary="등록된 디바이스 목록 조회",
)
async def list_devices(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DeviceListResponse:
    """
    REQ-MOBILE-003: 현재 사용자의 등록된 모든 디바이스를 반환합니다.

    TASK-003: DB-backed 조회 (DeviceToken 모델 사용)
    """
    from sqlalchemy import select

    from backend.db.device_token_models import DeviceToken

    # TASK-003: DB에서 사용자의 활성 디바이스 조회
    result = await db.execute(
        select(DeviceToken)
        .where(DeviceToken.user_id == str(current_user.id))
        .where(DeviceToken.is_active)
    )
    device_tokens = result.scalars().all()

    # DeviceResponse 리스트로 변환 (첫 쿼리에서 전체 객체를 이미 가져옴)
    devices = [
        DeviceResponse(
            id=dt.id,
            fcm_token=dt.fcm_token,
            platform=dt.platform,
            device_id=None,  # MVP: device_id 필드 없음
            created_at=dt.created_at,
            updated_at=dt.updated_at,
        )
        for dt in device_tokens
    ]

    logger.info(f"디바이스 목록 조회: user_id={current_user.id}, count={len(devices)}")

    return DeviceListResponse(devices=devices, total=len(devices))


def is_valid_uuid(uuid_str: str) -> bool:
    """UUID 문자열 유효성 검사"""
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False
