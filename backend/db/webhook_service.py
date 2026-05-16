"""
SPEC-WEBHOOK-001: 웹훅 엔드포인트 CRUD 서비스 (비동기 - API 레이어용)
"""

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.webhook_models import WebhookEndpoint
from backend.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate
from backend.utils.validators import validate_webhook_url

_MAX_WEBHOOKS_PER_USER = 20
_DELIVERY_TIMEOUT = 10  # 초


class WebhookService:
    """웹훅 엔드포인트 CRUD + 테스트 전송. 소유권 검증 포함."""

    async def _enforce_user_limit(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> None:
        stmt = select(func.count(WebhookEndpoint.id)).where(
            WebhookEndpoint.user_id == user_id
        )
        result = await session.execute(stmt)
        count = result.scalar_one()
        if count >= _MAX_WEBHOOKS_PER_USER:
            raise HTTPException(
                status_code=409,
                detail=f"웹훅은 사용자당 최대 {_MAX_WEBHOOKS_PER_USER}개까지 등록할 수 있습니다",
            )

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: WebhookEndpointCreate,
    ) -> WebhookEndpoint:
        await self._enforce_user_limit(session, user_id)

        endpoint = WebhookEndpoint()
        endpoint.id = uuid.uuid4()
        endpoint.user_id = user_id
        endpoint.url = payload.url
        endpoint.events = payload.events
        endpoint.secret = payload.secret
        endpoint.is_active = True
        endpoint.description = payload.description

        session.add(endpoint)
        await session.commit()
        await session.refresh(endpoint)
        return endpoint

    async def get_by_id(
        self,
        session: AsyncSession,
        webhook_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WebhookEndpoint:
        stmt = select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id)
        result = await session.execute(stmt)
        endpoint = result.scalar_one_or_none()
        if endpoint is None or endpoint.user_id != user_id:
            raise HTTPException(status_code=404, detail="웹훅 엔드포인트를 찾을 수 없습니다")
        return endpoint

    async def list_for_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[WebhookEndpoint], int]:
        base = select(WebhookEndpoint).where(WebhookEndpoint.user_id == user_id)
        count_base = select(func.count(WebhookEndpoint.id)).where(
            WebhookEndpoint.user_id == user_id
        )

        count_result = await session.execute(count_base)
        total = count_result.scalar_one()

        list_stmt = base.order_by(WebhookEndpoint.created_at.desc()).limit(limit).offset(offset)
        list_result = await session.execute(list_stmt)
        items = list(list_result.scalars().all())
        return items, total

    async def update(
        self,
        session: AsyncSession,
        webhook_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpoint:
        endpoint = await self.get_by_id(session, webhook_id, user_id)

        if payload.url is not None:
            endpoint.url = payload.url
        if payload.events is not None:
            endpoint.events = payload.events
        if payload.secret is not None:
            endpoint.secret = payload.secret
        if payload.is_active is not None:
            endpoint.is_active = payload.is_active
        if payload.description is not None:
            endpoint.description = payload.description

        await session.commit()
        await session.refresh(endpoint)
        return endpoint

    async def delete(
        self,
        session: AsyncSession,
        webhook_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        endpoint = await self.get_by_id(session, webhook_id, user_id)
        await session.delete(endpoint)
        await session.commit()

    async def ping(
        self,
        session: AsyncSession,
        webhook_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> tuple[int | None, bool, str]:
        """테스트 페이로드를 웹훅 URL로 전송. (status_code, success, message) 반환."""
        endpoint = await self.get_by_id(session, webhook_id, user_id)

        payload_dict = {
            "event": "ping",
            "webhook_id": str(endpoint.id),
            "timestamp": datetime.now(UTC).isoformat(),
            "message": "Voice-to-TextNote 웹훅 테스트",
        }
        body = json.dumps(payload_dict, ensure_ascii=False).encode()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VoiceToTextNote-Webhook/1.0",
            "X-Webhook-Event": "ping",
        }
        if endpoint.secret:
            sig = hmac.new(endpoint.secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={sig}"

        try:
            url = await asyncio.to_thread(
                validate_webhook_url,
                endpoint.url,
                resolve_host=True,
            )
            async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT) as client:
                resp = await client.post(url, content=body, headers=headers)
            success = resp.status_code < 400
            return resp.status_code, success, ("전송 성공" if success else f"HTTP {resp.status_code}")
        except ValueError as exc:
            return None, False, str(exc)
        except httpx.TimeoutException:
            return None, False, f"타임아웃 ({_DELIVERY_TIMEOUT}초 초과)"
        except Exception as exc:
            return None, False, f"연결 오류: {exc}"
