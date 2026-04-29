"""
SPEC-WEBHOOK-001: 웹훅 알림 동기 전송 서비스 - Celery 워커용

REQ-WEBHOOK-005: 작업 완료/실패 시 등록된 웹훅 URL로 자동 알림
REQ-WEBHOOK-006: 전송 실패는 무시 (best-effort, 작업 결과에 영향 없음)
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from backend.db.auth_models import MeetingOwnership
from backend.db.sync_engine import get_sync_session
from backend.db.webhook_models import WebhookEndpoint
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_DELIVERY_TIMEOUT = 10  # 초


def _build_payload(task_id: str, event_type: str, task_type: str, data: dict) -> bytes:
    """웹훅 페이로드 JSON 직렬화."""
    payload = {
        "event": f"{task_type}.{event_type}",
        "task_id": task_id,
        "task_type": task_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }
    return json.dumps(payload, ensure_ascii=False, default=str).encode()


def _make_signature(secret: str, body: bytes) -> str:
    """HMAC-SHA256 서명 생성."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _send_one(url: str, body: bytes, event_name: str, secret: str | None) -> None:
    """단일 웹훅 URL로 동기 HTTP POST 전송."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "VoiceToTextNote-Webhook/1.0",
        "X-Webhook-Event": event_name,
    }
    if secret:
        headers["X-Webhook-Signature"] = _make_signature(secret, body)

    with httpx.Client(timeout=_DELIVERY_TIMEOUT) as client:
        resp = client.post(url, content=body, headers=headers)

    if resp.status_code >= 400:
        logger.warning(
            "웹훅 전송 HTTP 오류",
            url=url,
            status_code=resp.status_code,
        )


def notify_webhooks_sync(
    task_id: str,
    event_type: str,
    task_type: str,
    data: dict,
) -> None:
    """
    # @MX:ANCHOR: Celery 워커에서 작업 완료 시 호출되는 웹훅 알림 진입점
    # @MX:REASON: transcription/diarization/minutes/summary 4개 워커가 모두 호출

    task_id와 연결된 소유자의 활성 웹훅 URL로 이벤트를 전송한다.
    모든 오류는 무시 (best-effort). 작업 결과에 절대 영향 없음.
    """
    event_name = f"{task_type}.{event_type}"
    try:
        with get_sync_session() as session:
            # 작업 소유자 조회
            owner_stmt = select(MeetingOwnership.owner_id).where(
                MeetingOwnership.task_id == task_id
            )
            owner_result = session.execute(owner_stmt)
            owner_row = owner_result.first()
            if owner_row is None:
                return  # 소유자 없음 (게스트 작업)

            owner_id = owner_row[0]

            # 소유자의 활성 웹훅 조회
            wh_stmt = select(WebhookEndpoint).where(
                WebhookEndpoint.user_id == owner_id,
                WebhookEndpoint.is_active.is_(True),
            )
            wh_result = session.execute(wh_stmt)
            endpoints = wh_result.scalars().all()

            if not endpoints:
                return

            body = _build_payload(task_id, event_type, task_type, data)

            for endpoint in endpoints:
                # events 필터: 빈 배열이면 전체 수신
                if endpoint.events and event_name not in endpoint.events:
                    continue
                try:
                    _send_one(endpoint.url, body, event_name, endpoint.secret)
                    logger.debug(
                        "웹훅 전송 완료",
                        webhook_id=str(endpoint.id),
                        url=endpoint.url,
                        event=event_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "웹훅 전송 실패 (무시)",
                        webhook_id=str(endpoint.id),
                        url=endpoint.url,
                        event=event_name,
                        error=str(exc),
                    )

    except Exception as exc:
        # DB 오류 등 전체 예외 무시
        logger.warning("웹훅 알림 처리 중 오류 (무시)", task_id=task_id, error=str(exc))
