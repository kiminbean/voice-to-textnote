"""
고급 검색 API
"""

from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import internal_server_error, not_found
from backend.app.exceptions import VoiceNoteError
from backend.schemas.advanced_search import (
    AdvancedSearchRequest,
    AdvancedSearchResponse,
    SavedSearch,
    SearchHistoryItem,
    SearchHistoryResponse,
)
from backend.services.advanced_search import AdvancedSearchService

router = APIRouter(prefix="/advanced-search", tags=["advanced_search"])


def get_advanced_search_service() -> AdvancedSearchService:
    """AdvancedSearchService 인스턴스 제공 (FastAPI Depends)"""
    return AdvancedSearchService()


@router.post("/search", response_model=AdvancedSearchResponse)
async def advanced_search(
    request: AdvancedSearchRequest,
    db: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AdvancedSearchService = Depends(get_advanced_search_service),
) -> AdvancedSearchResponse:
    """
    고급 검색 API

    다양한 필터와 정렬 옵션을 제공하는 고급 검색 기능
    """
    try:
        # 서비스 초기화
        await svc.initialize(redis_client)

        # 검색 실행
        results, pagination, analytics = await svc.search_advanced(request=request, db=db)

        # 쿼리 정보 생성
        query_info = {
            "query": request.query,
            "filters_applied": any(
                [
                    request.filters.start_date,
                    request.filters.end_date,
                    request.filters.speaker_ids,
                    request.filters.content_types,
                    request.filters.tags,
                    request.filters.min_word_count,
                    request.filters.max_word_count,
                ]
            ),
            "sort_by": request.sort_by,
            "sort_order": request.sort_order,
        }

        return AdvancedSearchResponse(
            results=results, pagination=pagination, analytics=analytics, query_info=query_info
        )

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"고급 검색 중 오류가 발생했습니다: {str(e)}")


@router.get("/history", response_model=SearchHistoryResponse)
async def get_search_history(
    limit: int = Query(default=50, ge=1, le=100, description="조회할 기록 수"),
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AdvancedSearchService = Depends(get_advanced_search_service),
) -> SearchHistoryResponse:
    """
    검색 기록 조회 API

    최근 검색 기록과 저장된 검색 목록을 조회
    """
    try:
        # 서비스 초기화
        await svc.initialize(redis_client)

        history_data = await svc.get_search_history(limit=limit)
        saved_search_data = await svc.get_saved_searches(limit=limit)

        history_items = []

        if history_data:
            for i, item in enumerate(history_data[:10]):
                history_items.append(
                    {
                        "id": item.get("id", f"hist_{i}"),
                        "query": item.get("query", "검색 쿼리"),
                        "filters": item.get("filters"),
                        "result_count": item.get("result_count", 0),
                        "search_time_ms": item.get("search_time_ms", 0.0),
                        "created_at": item.get("created_at") or datetime.now(UTC),
                        "is_saved": item.get("is_saved", False),
                    }
                )

        return SearchHistoryResponse(
            history=[SearchHistoryItem.model_validate(item) for item in history_items],
            saved_searches=[SavedSearch.model_validate(item) for item in saved_search_data],
        )

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"검색 기록 조회 중 오류가 발생했습니다: {str(e)}")


@router.post("/save-search")
async def save_search(
    search_id: str,
    name: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AdvancedSearchService = Depends(get_advanced_search_service),
) -> dict[str, Any]:
    """
    검색 저장 API

    자주 사용하는 검색 조건을 저장
    """
    try:
        await svc.initialize(redis_client)
        saved_data = await svc.save_search(search_id=search_id, name=name)
        if saved_data is None:
            not_found(f"검색 기록을 찾을 수 없습니다: {search_id}")

        return {"success": True, "message": "검색이 저장되었습니다", "saved_search": saved_data}

    except VoiceNoteError:
        raise  # pragma: no cover
    except Exception as e:
        internal_server_error(f"검색 저장 중 오류가 발생했습니다: {str(e)}")


@router.delete("/history/{history_id}")
async def delete_search_history(
    history_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    svc: AdvancedSearchService = Depends(get_advanced_search_service),
) -> dict[str, Any]:
    """
    검색 기록 삭제 API

    특정 검색 기록을 삭제
    """
    try:
        await svc.initialize(redis_client)
        await svc.delete_search_history(history_id)

        return {"success": True, "message": "검색 기록이 삭제되었습니다"}

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"검색 기록 삭제 중 오류가 발생했습니다: {str(e)}")
