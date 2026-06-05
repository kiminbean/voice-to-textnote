"""
고급 검색 API
"""

import time
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import internal_server_error
from backend.app.exceptions import VoiceNoteError
from backend.schemas.advanced_search import (
    AdvancedSearchRequest,
    AdvancedSearchResponse,
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

        # 검색 기록 조회
        history_data = await svc.get_search_history(limit=limit)

        # 간단한 가상 데이터 생성 (실제 Redis 데이터 대체)
        history_items = []
        saved_searches = []

        if history_data:
            for i, item in enumerate(history_data[:10]):
                history_items.append(
                    {
                        "id": item.get("id", f"hist_{i}"),
                        "query": item.get("query", "검색 쿼리"),
                        "filters": item.get("filters"),
                        "result_count": item.get("result_count", 0),
                        "search_time_ms": item.get("search_time_ms", 0.0),
                        "created_at": datetime.utcnow(),
                        "is_saved": item.get("is_saved", False),
                    }
                )

        # 저장된 검색 샘플 데이터
        saved_searches = [
            {
                "id": "saved_1",
                "name": "프로젝트 회의록 검색",
                "query": "프로젝트",
                "filters": {
                    "content_types": ["minutes"],
                    "start_date": datetime.utcnow() - timedelta(days=30),
                    "end_date": datetime.utcnow(),
                },
                "created_at": datetime.utcnow() - timedelta(days=7),
                "last_used_at": datetime.utcnow() - timedelta(days=1),
                "usage_count": 15,
            },
            {
                "id": "saved_2",
                "name": "중요 의사결정 검색",
                "query": "의사결정",
                "filters": {"content_types": ["summary"], "min_word_count": 100},
                "created_at": datetime.utcnow() - timedelta(days=14),
                "last_used_at": datetime.utcnow() - timedelta(days=5),
                "usage_count": 8,
            },
        ]

        return SearchHistoryResponse(history=history_items, saved_searches=saved_searches)

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"검색 기록 조회 중 오류가 발생했습니다: {str(e)}")


@router.post("/save-search")
async def save_search(
    search_id: str,
    name: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict[str, Any]:
    """
    검색 저장 API

    자주 사용하는 검색 조건을 저장
    """
    try:
        # 실제 구현에서는 검색 기록을 조회하고 업데이트
        saved_data = {
            "id": f"saved_{int(time.time())}",
            "name": name,
            "search_id": search_id,
            "created_at": datetime.utcnow(),
            "usage_count": 1,
        }

        # Redis에 저장 (실제 구현에서는 더 복잡한 로직이 필요)
        await redis_client.setex(
            f"saved_search:{saved_data['id']}",
            90 * 24 * 60 * 60,  # 90 days TTL
            str(saved_data),
        )

        return {"success": True, "message": "검색이 저장되었습니다", "saved_search": saved_data}

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"검색 저장 중 오류가 발생했습니다: {str(e)}")


@router.delete("/history/{history_id}")
async def delete_search_history(
    history_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> dict[str, Any]:
    """
    검색 기록 삭제 API

    특정 검색 기록을 삭제
    """
    try:
        # Redis에서 검색 기록 삭제
        await redis_client.delete(f"search_history:{history_id}")

        # 최근 검색 목록에서도 제거 (실제 구현에서는 더 복잡한 로직 필요)

        return {"success": True, "message": "검색 기록이 삭제되었습니다"}

    except VoiceNoteError:
        raise
    except Exception as e:
        internal_server_error(f"검색 기록 삭제 중 오류가 발생했습니다: {str(e)}")
