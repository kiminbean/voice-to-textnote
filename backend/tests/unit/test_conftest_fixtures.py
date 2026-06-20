"""Coverage for shared pytest fixtures used by unit tests."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_mock_redis_pipeline_returns_default_get_values(mock_redis_client):
    """The shared Redis mock pipeline mirrors get/get execution defaults."""
    mock_redis_client.get.return_value = "cached-value"

    pipeline = mock_redis_client.pipeline()
    pipeline.get("first").get("second")

    assert await pipeline.execute() == ["cached-value", "cached-value"]


def test_completed_task_data_fixture_shape(completed_task_data):
    """The completed task fixture exposes the result shape used by API tests."""
    assert completed_task_data["status"] == "completed"
    assert completed_task_data["language"] == "ko"
    assert completed_task_data["task_id"]
    assert completed_task_data["created_at"]
    assert completed_task_data["segments"][0]["text"] == "안녕하세요."


@pytest.mark.asyncio
async def test_db_session_fixture_executes_sql(db_session):
    """The async DB session fixture creates tables and yields a live session."""
    result = await db_session.execute(text("SELECT 1"))

    assert result.scalar_one() == 1
