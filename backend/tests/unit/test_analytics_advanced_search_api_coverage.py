"""
backend/app/api/v1/analytics/advanced_search.py API 단위 테스트

커버리지 대상:
- POST /advanced-search/search: 정상 검색, VoiceNoteError 전파, 일반 예외
- GET  /advanced-search/history: 정상 조회, 빈 기록, VoiceNoteError, 일반 예외
- POST /advanced-search/save-search: 정상 저장, 예외
- DELETE /advanced-search/history/{history_id}: 정상 삭제, 예외
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from backend.app.api.v1.analytics.advanced_search import (
    get_advanced_search_service,
    router,
)
from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.exceptions import VoiceNoteError
from backend.schemas.advanced_search import (
    SearchAnalytics,
    SearchResultItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_result_item(task_id: str = "t1") -> dict:
    return {
        "id": "uuid-001",
        "task_id": task_id,
        "title": "테스트 회의록",
        "content": "내용 미리보기",
        "content_type": "minutes",
        "speaker_ids": ["SPEAKER_00"],
        "word_count": 100,
        "tags": ["테스트"],
        "created_at": datetime(2026, 1, 15, 10, 30, 0).isoformat(),
        "relevance_score": 0.8,
        "highlights": ["테스트 회의록"],
    }


def _make_analytics() -> dict:
    return {
        "total_results": 1,
        "search_time_ms": 50.0,
        "distribution_by_type": {"minutes": 1},
        "distribution_by_speaker": {"SPEAKER_00": 1},
        "popular_tags": [{"tag": "테스트", "count": 1}],
        "average_word_count": 100.0,
        "search_trends": [
            {"period": "last_week", "searches": 150},
        ],
    }


def _make_pagination() -> dict:
    return {
        "page": 1,
        "page_size": 20,
        "total_results": 1,
        "has_next": False,
    }


async def _override_db_session():
    """DB 세션 mock override"""
    return AsyncMock()


async def _override_redis():
    """Redis mock override"""
    return AsyncMock()


def _create_app(
    svc_override=None,
    redis_override=None,
) -> FastAPI:
    """테스트용 FastAPI 앱 생성 with VoiceNoteError handler"""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # VoiceNoteError를 JSON 응답으로 변환하는 핸들러
    @app.exception_handler(VoiceNoteError)
    async def voice_note_error_handler(request: Request, exc: VoiceNoteError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message},
        )

    if svc_override is not None:
        app.dependency_overrides[get_advanced_search_service] = lambda: svc_override

    if redis_override is not None:
        app.dependency_overrides[get_redis_client] = lambda: redis_override
    else:
        app.dependency_overrides[get_redis_client] = _override_redis

    app.dependency_overrides[get_db_session] = _override_db_session

    return app


def _build_search_body(**overrides) -> dict:
    """기본 검색 요청 바디 생성"""
    body = {
        "query": "테스트",
        "filters": {},
        "sort_by": "relevance",
        "sort_order": "desc",
        "page": 1,
        "page_size": 20,
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# POST /search 테스트
# ---------------------------------------------------------------------------


class TestAdvancedSearchEndpoint:
    """POST /advanced-search/search 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """정상 검색 요청"""
        mock_svc = AsyncMock()
        result_items = [SearchResultItem(**_make_search_result_item())]
        pagination = _make_pagination()
        analytics = SearchAnalytics(**_make_analytics())
        mock_svc.search_advanced.return_value = (result_items, pagination, analytics)

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "pagination" in data
        assert "analytics" in data
        assert "query_info" in data
        assert data["query_info"]["query"] == "테스트"

    @pytest.mark.asyncio
    async def test_search_with_filters_applied(self):
        """필터가 적용된 검색 — filters_applied=True"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(
                    filters={
                        "start_date": "2026-01-01T00:00:00",
                        "end_date": "2026-12-31T23:59:59",
                        "content_types": ["minutes"],
                    },
                    sort_by="date",
                ),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_info"]["filters_applied"] is True
        assert data["query_info"]["sort_by"] == "date"

    @pytest.mark.asyncio
    async def test_search_no_filters_applied(self):
        """필터 미사용 시 filters_applied=False"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_info"]["filters_applied"] is False

    @pytest.mark.asyncio
    async def test_search_voice_note_error_propagates(self):
        """VoiceNoteError 발생 시 해당 status_code로 응답"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.side_effect = VoiceNoteError(
            error_code="TEST_ERROR",
            message="테스트 에러",
            status_code=400,
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(),
            )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error_code"] == "TEST_ERROR"

    @pytest.mark.asyncio
    async def test_search_generic_exception_returns_500(self):
        """일반 예외 발생 시 internal_server_error 헬퍼가 500 응답"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.side_effect = RuntimeError("DB 연결 실패")

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(),
            )

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_search_query_info_contains_sort_info(self):
        """query_info에 sort 정보 포함"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(sort_by="date", sort_order="asc"),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_info"]["sort_by"] == "date"
        assert data["query_info"]["sort_order"] == "asc"

    @pytest.mark.asyncio
    async def test_search_tag_filter_flags_applied(self):
        """tags 필터 포함 시 filters_applied=True"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(filters={"tags": ["중요"]}),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["query_info"]["filters_applied"] is True

    @pytest.mark.asyncio
    async def test_search_min_word_count_filter_flags_applied(self):
        """min_word_count 필터 포함 시 filters_applied=True"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(filters={"min_word_count": 50}),
            )

        assert resp.status_code == 200
        assert resp.json()["query_info"]["filters_applied"] is True

    @pytest.mark.asyncio
    async def test_search_speaker_ids_filter_flags_applied(self):
        """speaker_ids 필터 포함 시 filters_applied=True"""
        mock_svc = AsyncMock()
        mock_svc.search_advanced.return_value = (
            [],
            _make_pagination(),
            SearchAnalytics(**_make_analytics()),
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/search",
                json=_build_search_body(filters={"speaker_ids": ["spk1"]}),
            )

        assert resp.status_code == 200
        assert resp.json()["query_info"]["filters_applied"] is True


# ---------------------------------------------------------------------------
# GET /history 테스트
# ---------------------------------------------------------------------------


class TestGetHistoryEndpoint:
    """GET /advanced-search/history 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_history_success_with_data(self):
        """검색 기록 정상 조회"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.return_value = [
            {
                "id": "hist_1",
                "query": "테스트 쿼리",
                "filters": None,
                "result_count": 5,
                "search_time_ms": 100.0,
                "is_saved": False,
            }
        ]

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history?limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "saved_searches" in data
        assert len(data["history"]) == 1
        assert data["history"][0]["query"] == "테스트 쿼리"

    @pytest.mark.asyncio
    async def test_history_empty(self):
        """빈 검색 기록"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.return_value = []

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history?limit=50")

        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []
        assert len(data["saved_searches"]) == 2  # 하드코딩 샘플 데이터

    @pytest.mark.asyncio
    async def test_history_generic_exception(self):
        """일반 예외 발생 시 500"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.side_effect = RuntimeError("Redis 오류")

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_history_limit_default_50(self):
        """기본 limit=50 동작 확인"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.return_value = []

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history")

        assert resp.status_code == 200
        mock_svc.get_search_history.assert_called_once_with(limit=50)

    @pytest.mark.asyncio
    async def test_history_saved_searches_structure(self):
        """saved_searches에 샘플 데이터 2개 포함 확인"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.return_value = []

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history")

        data = resp.json()
        saved = data["saved_searches"]
        assert len(saved) == 2
        assert saved[0]["id"] == "saved_1"
        assert saved[1]["id"] == "saved_2"

    @pytest.mark.asyncio
    async def test_history_voice_note_error_propagates(self):
        """VoiceNoteError 발생 시 해당 status_code로 응답"""
        mock_svc = AsyncMock()
        mock_svc.get_search_history.side_effect = VoiceNoteError(
            error_code="NOT_FOUND",
            message="기록 없음",
            status_code=404,
        )

        app = _create_app(svc_override=mock_svc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/advanced-search/history")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /save-search 테스트
# ---------------------------------------------------------------------------


class TestSaveSearchEndpoint:
    """POST /advanced-search/save-search 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_save_search_success(self):
        """검색 저장 성공"""
        mock_redis = AsyncMock()
        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/save-search",
                params={"search_id": "search_123", "name": "내 검색"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["saved_search"]["name"] == "내 검색"
        assert data["saved_search"]["search_id"] == "search_123"
        # Redis에 setex가 호출되었는지 확인
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_save_search_exception_returns_500(self):
        """저장 중 예외 발생 시 500"""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = RuntimeError("Redis 연결 실패")

        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/save-search",
                params={"search_id": "search_123", "name": "내 검색"},
            )

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_save_search_response_structure(self):
        """저장 응답 구조 확인"""
        mock_redis = AsyncMock()
        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/advanced-search/save-search",
                params={"search_id": "sid_001", "name": "테스트"},
            )

        data = resp.json()
        assert "success" in data
        assert "message" in data
        assert "saved_search" in data
        assert data["saved_search"]["id"].startswith("saved_")
        assert data["saved_search"]["usage_count"] == 1


# ---------------------------------------------------------------------------
# DELETE /history/{history_id} 테스트
# ---------------------------------------------------------------------------


class TestDeleteHistoryEndpoint:
    """DELETE /advanced-search/history/{history_id} 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """검색 기록 삭제 성공"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1

        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/advanced-search/history/hist_123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "삭제" in data["message"]
        mock_redis.delete.assert_called_once_with("search_history:hist_123")

    @pytest.mark.asyncio
    async def test_delete_exception_returns_500(self):
        """삭제 중 예외 발생 시 500"""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = RuntimeError("Redis 오류")

        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/advanced-search/history/hist_123")

        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_voice_note_error_propagates(self):
        """VoiceNoteError 발생 시 해당 status_code로 응답"""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = VoiceNoteError(
            error_code="FORBIDDEN",
            message="삭제 권한 없음",
            status_code=403,
        )

        app = _create_app(redis_override=mock_redis)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete("/api/v1/advanced-search/history/hist_123")

        assert resp.status_code == 403
