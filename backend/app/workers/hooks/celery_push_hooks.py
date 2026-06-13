"""
SPEC-MOBILE-001: Celery Push 알림 훅

REQ-MOBILE-002-08: on_success hook — meeting_id 포함 payload로 Push 전송
REQ-MOBILE-002-09: on_failure hook — 에러 정보 포함 Push 전송

설계:
- Push 전송 실패가 파이프라인 완료 자체에 영향을 주지 않도록 격리
- user_id가 파이프라인에 전달되면 즉시 활성화 가능
- MVP: user_id를 Redis에서 조회하거나 직접 전달받는 구조
"""

import asyncio
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _fire_push_async(
    user_id: str,
    meeting_id: str,
    task_id: str,
    status: str,
    error_message: str = "",
) -> None:
    """비동기 Push 훅을 새 이벤트 루프에서 실행 (Celery 동기 컨텍스트용)"""
    try:
        loop = asyncio.new_event_loop()
        try:
            if status == "completed":
                loop.run_until_complete(
                    on_pipeline_success(
                        user_id=user_id,
                        meeting_id=meeting_id,
                        task_id=task_id,
                    )
                )
            elif status == "failed":
                loop.run_until_complete(
                    on_pipeline_failure(
                        user_id=user_id,
                        meeting_id=meeting_id,
                        task_id=task_id,
                        error_message=error_message,
                    )
                )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Push 훅 실행 오류 (무시): {e}")


def fire_push_sync(
    user_id: str | None,
    meeting_id: str,
    task_id: str,
    status: str,
    error_message: str = "",
) -> None:
    """Celery 워커 동기 컨텍스트에서 호출하는 Push 훅 진입점 (best-effort)"""
    if user_id is None:
        return

    try:
        _fire_push_async(user_id, meeting_id, task_id, status, error_message)
    except Exception as e:
        logger.error(f"fire_push_sync 오류 (파이프라인 영향 없음): {e}")


async def on_pipeline_success(
    user_id: str,
    meeting_id: str,
    task_id: str,
    db_session: Any = None,
) -> bool:
    """
    REQ-MOBILE-002-08: 파이프라인 정상 완료 시 Push 알림 전송

    Args:
        user_id: 사용자 ID (FCM 토큰 조회용)
        meeting_id: 회의 ID (딥링크 payload)
        task_id: Celery 작업 ID (로깅용)
        db_session: AsyncSession (DB에서 토큰 조회)

    Returns:
        전송 성공 여부 (실패해도 파이프라인에 영향 없음)
    """
    if db_session is None:
        logger.warning(
            f"Push 훅: DB 세션 없음 — user_id={user_id}, meeting_id={meeting_id}, task_id={task_id}"
        )
        return False

    try:
        from backend.services.push_service import get_push_service

        push_service = get_push_service()
        result = await push_service.send_to_user(
            db=db_session,
            user_id=user_id,
            meeting_id=meeting_id,
            title="회의록 처리 완료",
            body="회의록이 성공적으로 생성되었습니다. 탭하여 확인하세요.",
            data={"task_id": task_id, "type": "pipeline_complete"},
        )

        logger.info(
            f"Push 전송 완료: user_id={user_id}, meeting_id={meeting_id}, "
            f"success={result['success_count']}, failure={result['failure_count']}"
        )
        return result["success_count"] > 0

    except Exception as e:
        # Push 전송 실패가 파이프라인에 영향을 주지 않도록 격리
        logger.error(
            f"Push 전송 실패 (파이프라인 영향 없음): "
            f"user_id={user_id}, meeting_id={meeting_id}, error={e}"
        )
        return False


async def on_pipeline_failure(
    user_id: str,
    meeting_id: str,
    task_id: str,
    error_message: str = "",
    db_session: Any = None,
) -> bool:
    """
    REQ-MOBILE-002-09: 파이프라인 실패 시 Push 알림 전송

    Args:
        user_id: 사용자 ID
        meeting_id: 회의 ID
        task_id: Celery 작업 ID
        error_message: 에러 메시지
        db_session: AsyncSession

    Returns:
        전송 성공 여부
    """
    if db_session is None:
        logger.warning(f"Push 실패 훅: DB 세션 없음 — user_id={user_id}, task_id={task_id}")
        return False

    try:
        from backend.services.push_service import get_push_service

        push_service = get_push_service()
        result = await push_service.send_to_user(
            db=db_session,
            user_id=user_id,
            meeting_id=meeting_id,
            title="회의록 처리 실패",
            body=f"처리 중 오류가 발생했습니다: {error_message[:50]}",
            data={
                "task_id": task_id,
                "type": "pipeline_failed",
                "error": error_message[:200],
            },
        )

        logger.info(
            f"Push 실패 알림 전송: user_id={user_id}, meeting_id={meeting_id}, "
            f"success={result['success_count']}"
        )
        return result["success_count"] > 0

    except Exception as e:
        logger.error(f"Push 실패 알림 전송 오류 (무시): user_id={user_id}, error={e}")
        return False


def get_push_hook_summary(
    user_id: str,
    meeting_id: str,
    task_id: str,
    status: str,
) -> dict[str, str]:
    """
    Push 훅 메타데이터 생성 (로깅/모니터링용)

    Returns:
        훅 실행 컨텍스트 딕셔너리
    """
    return {
        "user_id": user_id,
        "meeting_id": meeting_id,
        "task_id": task_id,
        "status": status,
        "hook_version": "1.0.0",
    }
