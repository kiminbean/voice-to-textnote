"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 관리 API

엔드포인트 (모두 JWT 인증 필요):
- POST   /api/v1/webhooks                    등록
- GET    /api/v1/webhooks                    목록
- GET    /api/v1/webhooks/{id}               단건 조회
- PATCH  /api/v1/webhooks/{id}               부분 수정
- DELETE /api/v1/webhooks/{id}               삭제
- POST   /api/v1/webhooks/{id}/ping          테스트 전송
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.schemas.webhook import (
    WebhookEndpointCreate,
    WebhookEndpointListResponse,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
    WebhookPingResponse,
)
from backend.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_webhook_service() -> WebhookService:
    """WebhookService 인스턴스 제공 (FastAPI Depends)"""
    return WebhookService()


@router.post(
    "",
    response_model=WebhookEndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    payload: WebhookEndpointCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> WebhookEndpointResponse:
    """REQ-WEBHOOK-001: 웹훅 엔드포인트 등록."""
    endpoint = await svc.create(db, user.id, payload)
    return WebhookEndpointResponse.from_orm_masked(endpoint)


@router.get("", response_model=WebhookEndpointListResponse)
async def list_webhooks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> WebhookEndpointListResponse:
    """REQ-WEBHOOK-002: 등록된 웹훅 목록 조회."""
    offset = (page - 1) * page_size
    items, total = await svc.list_for_user(
        session=db,
        user_id=user.id,
        limit=page_size,
        offset=offset,
    )
    return WebhookEndpointListResponse(
        items=[WebhookEndpointResponse.from_orm_masked(item) for item in items],
        total=total,
    )


@router.get("/{webhook_id}", response_model=WebhookEndpointResponse)
async def get_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> WebhookEndpointResponse:
    endpoint = await svc.get_by_id(db, webhook_id, user.id)
    return WebhookEndpointResponse.from_orm_masked(endpoint)


@router.patch("/{webhook_id}", response_model=WebhookEndpointResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    payload: WebhookEndpointUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> WebhookEndpointResponse:
    endpoint = await svc.update(db, webhook_id, user.id, payload)
    return WebhookEndpointResponse.from_orm_masked(endpoint)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> None:
    await svc.delete(db, webhook_id, user.id)


@router.post("/{webhook_id}/ping", response_model=WebhookPingResponse)
async def ping_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: WebhookService = Depends(get_webhook_service),
) -> WebhookPingResponse:
    """REQ-WEBHOOK-007: 등록된 URL로 테스트 페이로드 전송."""
    endpoint = await svc.get_by_id(db, webhook_id, user.id)
    status_code, success, message = await svc.ping(db, webhook_id, user.id)
    return WebhookPingResponse(
        webhook_id=endpoint.id,
        url=endpoint.url,
        status_code=status_code,
        success=success,
        message=message,
    )
