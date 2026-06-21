"""Direct API branch coverage for smart summary endpoints."""

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.api.v1.minutes import smart_summary as api
from backend.app.exceptions import VoiceNoteError
from backend.schemas.smart_summary import (
    FocusArea,
    MeetingDetection,
    MeetingType,
    SentimentAnalysis,
    SummaryContent,
    SummaryGenerationResult,
    SummaryLength,
    SummaryMode,
    SummaryRequest,
)


def _db_result(record):
    scalars = SimpleNamespace(first=lambda: record)
    return SimpleNamespace(scalars=lambda: scalars)


def _summary_result() -> SummaryGenerationResult:
    return SummaryGenerationResult(
        task_id="generated-1",
        summary_mode=SummaryMode.EXECUTIVE,
        length=SummaryLength.MEDIUM,
        meeting_detection=MeetingDetection(
            detected_type=MeetingType.PLANNING,
            confidence=0.82,
            reasoning=["planning keyword"],
            keywords=["plan"],
        ),
        summary_content=SummaryContent(
            summary_text="요약",
            key_points=["핵심"],
            action_items=["실행"],
            decisions=["결정"],
            participants_mentioned=["Kim"],
            topics_covered=["Roadmap"],
            word_count=10,
            reading_time_minutes=0.5,
        ),
        sentiment_analysis=SentimentAnalysis(
            overall_sentiment="positive",
            sentiment_score=0.4,
            sentiment_details={"positive": 1},
            emotional_segments=[],
        ),
        confidence_score=0.9,
        processing_time_seconds=0.2,
        metadata={"source": "test"},
    )


def _request() -> SummaryRequest:
    return SummaryRequest(
        summary_mode=SummaryMode.EXECUTIVE,
        length=SummaryLength.MEDIUM,
        focus_areas=[FocusArea.ALL],
    )


def test_parse_status_accepts_redis_bytes_and_rejects_non_object_payload():
    assert api._parse_status(b'{"task_id": "task-1"}') == {"task_id": "task-1"}

    with pytest.raises(ValueError, match="not an object"):
        api._parse_status('["not", "an", "object"]')


@pytest.mark.asyncio
async def test_create_smart_summary_uses_markdown_and_stores_completed_status():
    record = SimpleNamespace(result_data={"markdown": "# 회의록\n내용"})
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_db_result(record))
    redis = AsyncMock()
    svc = AsyncMock()
    svc.generate_smart_summary = AsyncMock(return_value=_summary_result())

    response = await api.create_smart_summary(
        minutes_task_id="minutes-1",
        request=_request(),
        db=db,
        redis_client=redis,
        svc=svc,
    )

    assert response.status == "completed"
    assert response.result.summary_content.summary_text == "요약"
    assert response.detected_meeting_type == MeetingType.PLANNING
    svc.generate_smart_summary.assert_awaited_once_with("# 회의록\n내용", _request())
    assert redis.setex.await_count == 2
    completed_payload = json.loads(redis.setex.await_args.args[2])
    assert completed_payload["status"] == "completed"
    assert completed_payload["progress"] == 100.0


@pytest.mark.asyncio
async def test_create_smart_summary_uses_text_or_segments_and_reports_input_errors():
    svc = AsyncMock()
    redis = AsyncMock()

    for result_data, expected_content in [
        ({"text": "plain text"}, "plain text"),
        ({"segments": [{"text": "one"}, {"text": "two"}]}, "one\ntwo"),
    ]:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_db_result(SimpleNamespace(result_data=result_data)))
        svc.generate_smart_summary = AsyncMock(return_value=_summary_result())

        await api.create_smart_summary("minutes-1", _request(), db, redis, svc)

        assert svc.generate_smart_summary.await_args.args[0] == expected_content

    for record in [
        None,
        SimpleNamespace(result_data={}),
        SimpleNamespace(result_data={"text": " "}),
    ]:
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_db_result(record))
        with pytest.raises(VoiceNoteError):
            await api.create_smart_summary("missing", _request(), db, redis, svc)


@pytest.mark.asyncio
async def test_create_smart_summary_persists_failed_status_when_service_raises():
    record = SimpleNamespace(result_data={"markdown": "content"})
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_db_result(record))
    redis = AsyncMock()
    svc = AsyncMock()
    svc.generate_smart_summary = AsyncMock(side_effect=RuntimeError("generation failed"))

    with pytest.raises(RuntimeError, match="generation failed"):
        await api.create_smart_summary("minutes-1", _request(), db, redis, svc)

    failed_payload = json.loads(redis.setex.await_args.args[2])
    assert failed_payload["status"] == "failed"
    assert failed_payload["error_message"] == "generation failed"


@pytest.mark.asyncio
async def test_get_smart_summary_status_handles_success_missing_and_parse_error():
    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=str(
            {
                "task_id": "task-1",
                "status": "processing",
                "progress": 42.0,
                "current_step": "analysis",
                "estimated_remaining_seconds": 9.5,
                "error_message": None,
            }
        )
    )

    status = await api.get_smart_summary_status("task-1", redis)

    assert status.task_id == "task-1"
    assert status.progress_percent == 42.0
    assert status.estimated_remaining_seconds == 9.5

    redis.get = AsyncMock(return_value=None)
    with pytest.raises(VoiceNoteError, match="찾을 수 없습니다"):
        await api.get_smart_summary_status("missing", redis)

    redis.get = AsyncMock(return_value="{bad")
    with pytest.raises(VoiceNoteError, match="파싱 실패"):
        await api.get_smart_summary_status("bad", redis)


@pytest.mark.asyncio
async def test_get_smart_summary_result_rehydrates_completed_payload():
    result = _summary_result()
    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=str(
            {
                "task_id": "task-1",
                "status": "completed",
                "summary_request": _request().model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
                "detected_meeting_type": "planning",
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:00:01",
            }
        )
    )

    response = await api.get_smart_summary_result("task-1", redis)

    assert response.status == "completed"
    assert response.result.confidence_score == 0.9
    assert response.detected_meeting_type == MeetingType.PLANNING
    assert response.completed_at == datetime.fromisoformat("2026-01-01T00:00:01")


@pytest.mark.asyncio
async def test_get_smart_summary_result_rejects_missing_bad_or_incomplete_payloads():
    redis = AsyncMock()

    redis.get = AsyncMock(return_value=None)
    with pytest.raises(VoiceNoteError, match="찾을 수 없습니다"):
        await api.get_smart_summary_result("missing", redis)

    redis.get = AsyncMock(return_value="{bad")
    with pytest.raises(VoiceNoteError, match="파싱 실패"):
        await api.get_smart_summary_result("bad", redis)

    redis.get = AsyncMock(return_value=str({"task_id": "task-1", "status": "processing"}))
    with pytest.raises(VoiceNoteError, match="완료되지"):
        await api.get_smart_summary_result("task-1", redis)


@pytest.mark.asyncio
async def test_get_available_meeting_types_returns_all_enum_values():
    response = await api.get_available_meeting_types()

    values = {item["value"] for item in response["meeting_types"]}
    assert values == {meeting_type.value for meeting_type in MeetingType}
    assert all(item["keywords"] for item in response["meeting_types"])


@pytest.mark.asyncio
async def test_get_available_summary_modes_returns_owll_benchmark_presets():
    response = await api.get_available_summary_modes()

    modes = response["modes"]
    values = {item["value"] for item in modes}
    assert values == {summary_mode.value for summary_mode in SummaryMode}
    assert len(modes) >= 10
    assert {
        "value": "lecture_notes",
        "label": "강의 노트",
        "description": "학습과 복습에 맞춘 노트 구조입니다.",
    } in modes
    assert {
        "value": "sales_follow_up",
        "label": "영업 후속",
        "description": "고객 니즈와 다음 연락 액션을 정리합니다.",
    } in modes
    assert {
        "value": "action_only",
        "label": "액션만",
        "description": "실행 항목만 빠르게 추출합니다.",
    } in modes
