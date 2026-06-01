"""
SPEC-QA-001: 회의 Q&A API 엔드포인트

엔드포인트:
- POST /api/v1/qa/ask          질문하기
- GET  /api/v1/qa/{task_id}/history  이력 조회
"""

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.dependencies import get_redis_client
from backend.schemas.qa import MeetingAskRequest, MeetingAskResponse, QAHistoryResponse
from backend.services.qa_service import QAService

router = APIRouter(prefix="/qa", tags=["qa"])

_service = QAService()


@router.post(
    "/ask",
    response_model=MeetingAskResponse,
    responses={404: {"description": "회의록 없음"}},
)
async def ask_question(
    payload: MeetingAskRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> MeetingAskResponse:
    """회의 내용에 대해 자연어 질문하기."""
    try:
        return await _service.ask(
            task_id=payload.task_id,
            question=payload.question,
            redis_client=redis_client,
            thread_id=payload.thread_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Q&A 처리 중 오류가 발생했습니다: {e}",
        )


@router.get(
    "/{task_id}/history",
    response_model=QAHistoryResponse,
)
async def get_qa_history(
    task_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> QAHistoryResponse:
    """회의 Q&A 이력 조회."""
    return await _service.get_history(task_id, redis_client)
