"""
SPEC-ACTION-001: 액션 아이템 추출 API

엔드포인트:
- POST /api/v1/action-items/extract    텍스트에서 액션 아이템 추출
- POST /api/v1/action-items/meeting     기존 회의록에서 액션 아이템 추출
"""

import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status

from backend.app.dependencies import get_redis_client
from backend.app.errors import internal_server_error, not_found, unprocessable
from backend.app.exceptions import VoiceNoteError
from backend.ml.action_items_engine import extract_action_items
from backend.schemas.action_items import (
    ActionItem,
    ActionItemExtractRequest,
    ActionItemFromMeetingRequest,
    ActionItemsResponse,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/action-items", tags=["action-items"])


@router.post(
    "/extract",
    response_model=ActionItemsResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_action_items_api(
    request: ActionItemExtractRequest,
) -> ActionItemsResponse:
    """
    텍스트에서 액션 아이템 추출

    회의록, STT 결과 등 텍스트를 입력받아
    할 일, 담당자, 기한, 우선순위를 자동 추출합니다.
    """
    try:
        items = extract_action_items(
            text=request.text,
            language=request.language,
            include_deadlines=request.include_deadlines,
            include_assignees=request.include_assignees,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error("액션 아이템 추출 실패", error=str(e))
        internal_server_error(f"액션 아이템 추출 중 오류 발생: {e}")

    action_items = [
        ActionItem(
            id=i + 1,
            task=item.task,
            assignee=item.assignee,
            deadline=item.deadline,
            priority=item.priority,
            context=item.context,
        )
        for i, item in enumerate(items)
    ]

    logger.info(
        "액션 아이템 추출 완료",
        total=len(action_items),
        language=request.language,
    )

    return ActionItemsResponse(
        task_id=str(uuid.uuid4()),
        status="completed",
        action_items=action_items,
        total_count=len(action_items),
        extracted_at=datetime.now(UTC).isoformat(),
    )


@router.post(
    "/meeting",
    response_model=ActionItemsResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_from_meeting(
    request: ActionItemFromMeetingRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> ActionItemsResponse:
    """
    기존 회의록에서 액션 아이템 추출

    minutes_task_id로 저장된 회의록 결과를 조회하여
    액션 아이템을 추출합니다.
    """
    # Redis에서 회의록 결과 조회
    cache_key = f"minutes:{request.minutes_task_id}"
    result_data = await redis_client.get(cache_key)

    if not result_data:
        not_found(f"회의록 결과를 찾을 수 없습니다: {request.minutes_task_id}")

    import json

    try:
        minutes_data = json.loads(result_data)
    except json.JSONDecodeError as e:
        internal_server_error("회의록 데이터 파싱 실패")

    # 회의록 텍스트 추출 (결과 구조에 맞게)
    text_parts = []
    if isinstance(minutes_data, dict):
        # 전사 텍스트
        if "transcription" in minutes_data:
            text_parts.append(str(minutes_data["transcription"]))
        if "text" in minutes_data:
            text_parts.append(str(minutes_data["text"]))
        if "segments" in minutes_data:
            segments = minutes_data["segments"]
            if isinstance(segments, list):
                for seg in segments:
                    if isinstance(seg, dict) and "text" in seg:
                        text_parts.append(seg["text"])
        # 회의록 본문
        if "minutes" in minutes_data:
            minutes_content = minutes_data["minutes"]
            if isinstance(minutes_content, str):
                text_parts.append(minutes_content)
            elif isinstance(minutes_content, dict) and "content" in minutes_content:
                text_parts.append(minutes_content["content"])

    full_text = "\n".join(text_parts)

    if len(full_text.strip()) < 10:
        unprocessable("회의록 내용이 너무 짧아 액션 아이템을 추출할 수 없습니다")

    # 언어 감지 (간단히 한국어 비율 확인)
    ko_chars = sum(1 for c in full_text if "\uac00" <= c <= "\ud7af")
    language = "ko" if ko_chars > len(full_text) * 0.1 else "en"

    items = extract_action_items(
        text=full_text,
        language=language,
        include_deadlines=request.include_deadlines,
        include_assignees=request.include_assignees,
    )

    action_items = [
        ActionItem(
            id=i + 1,
            task=item.task,
            assignee=item.assignee,
            deadline=item.deadline,
            priority=item.priority,
            context=item.context,
        )
        for i, item in enumerate(items)
    ]

    logger.info(
        "회의록 액션 아이템 추출 완료",
        minutes_task_id=request.minutes_task_id,
        total=len(action_items),
    )

    return ActionItemsResponse(
        task_id=str(uuid.uuid4()),
        status="completed",
        action_items=action_items,
        total_count=len(action_items),
        extracted_at=datetime.now(UTC).isoformat(),
    )
