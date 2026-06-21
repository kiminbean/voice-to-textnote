from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.schemas.external_import import ExternalImportSourceType, ExternalTextImportRequest
from backend.services.external_import_service import (
    ExternalImportService,
    ExternalImportValidationError,
)


@pytest.mark.asyncio
async def test_import_text_persists_minutes_result_and_caches_for_existing_flow():
    service = ExternalImportService()
    db = AsyncMock()
    redis = AsyncMock()
    db.run_sync = AsyncMock()
    db.commit = AsyncMock()
    payload = ExternalTextImportRequest(
        source_url="https://youtu.be/example123",
        title="제품 데모 영상",
        content="첫 번째 문단입니다.\n\n두 번째 문단에서는 고객 피드백과 다음 단계를 설명합니다.",
    )

    with patch(
        "backend.services.external_import_service.ResultService.save_result",
        new_callable=AsyncMock,
    ) as save_result:
        response = await service.import_text(payload, db, redis)

    assert response.task_id.startswith("ext-")
    assert response.status == "completed"
    assert response.source_type == ExternalImportSourceType.YOUTUBE
    assert response.result_url == f"/api/v1/minutes/{response.task_id}"
    assert response.search_indexed is True

    saved_kwargs = save_result.await_args.kwargs
    result_data = saved_kwargs["result_data"]
    assert saved_kwargs["task_type"] == "minutes"
    assert saved_kwargs["status"] == "completed"
    assert saved_kwargs["input_metadata"]["source"] == "external_import"
    assert result_data["source"]["type"] == "youtube"
    assert result_data["segments"][0]["speaker_name"] == "외부 소스"
    assert "고객 피드백" in result_data["segments"][0]["text"]
    assert "원본: https://youtu.be/example123" in result_data["markdown"]
    assert redis.setex.await_count == 2
    assert db.run_sync.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_text_reports_search_index_best_effort_failure():
    service = ExternalImportService()
    db = AsyncMock()
    redis = AsyncMock()
    db.run_sync = AsyncMock(side_effect=RuntimeError("fts unavailable"))
    db.rollback = AsyncMock()
    payload = ExternalTextImportRequest(
        source_url="https://example.com/transcript",
        title="외부 기사",
        content="검색 인덱스 실패와 무관하게 가져오기 결과는 저장되어야 합니다.",
    )

    with patch(
        "backend.services.external_import_service.ResultService.save_result",
        new_callable=AsyncMock,
    ):
        response = await service.import_text(payload, db, redis)

    assert response.search_indexed is False
    db.rollback.assert_awaited_once()


def test_normalize_content_rejects_empty_import_text():
    service = ExternalImportService()

    with pytest.raises(ExternalImportValidationError):
        if not service._normalize_content(" \n\t "):
            raise ExternalImportValidationError("가져올 본문이 비어 있습니다.")


@pytest.mark.asyncio
async def test_import_text_rejects_whitespace_after_normalization():
    service = ExternalImportService()

    with pytest.raises(ExternalImportValidationError, match="본문"):
        await service.import_text(
            SimpleNamespace(content=" \n\t "),
            AsyncMock(),
            AsyncMock(),
        )


def test_resolve_source_type_respects_explicit_non_web_type():
    service = ExternalImportService()

    assert (
        service._resolve_source_type(
            "https://example.com/video",
            ExternalImportSourceType.PODCAST,
        )
        == ExternalImportSourceType.PODCAST
    )
