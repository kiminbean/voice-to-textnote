"""
마인드맵 Celery 태스크 단위 테스트.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

MOCK_SUMMARY_RESULT = {
    "task_id": "summary-task-1",
    "status": "completed",
    "summary_text": "제품 출시 회의 요약",
    "sections": {"결정": "베타 출시 유지"},
    "action_items": [],
    "key_decisions": ["베타 출시 유지"],
    "next_steps": ["QA 일정 확정"],
}


def _make_mock_redis(summary_task_id: str, summary_result: dict | None = None) -> MagicMock:
    mock = MagicMock()
    mock.get.side_effect = lambda key: (
        json.dumps(summary_result)
        if summary_result and key == f"task:sum:result:{summary_task_id}"
        else None
    )
    mock.setex.return_value = True
    mock.publish.return_value = 1
    return mock


def _make_mock_generator():
    from backend.schemas.summary import MindMapEdge, MindMapNode

    root = MindMapNode(
        id="root",
        title="제품 출시",
        summary="출시 결정과 후속 QA",
        source_refs=["summary_text"],
    )
    edges = [MindMapEdge(source="root", target="qa", relation="leads_to")]

    mock_cls = MagicMock()
    mock_cls.return_value.generate_mind_map.return_value = (root, edges)
    return mock_cls


class TestMindMapTaskHappyPath:
    def test_task_returns_completed_result(self):
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = "summary-task-1"
        mock_redis = _make_mock_redis(summary_task_id, MOCK_SUMMARY_RESULT)

        with patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.mind_map_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"
                with patch(
                    "backend.workers.tasks.mind_map_task.MindMapGenerator",
                    _make_mock_generator(),
                ):
                    result = mind_map_task(task_id, summary_task_id)

        assert result["status"] == "completed"
        assert result["root"]["id"] == "root"
        assert result["edges"][0]["relation"] == "leads_to"

    def test_task_caches_mind_map_result(self):
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = "summary-task-1"
        mock_redis = _make_mock_redis(summary_task_id, MOCK_SUMMARY_RESULT)

        with patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.mind_map_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"
                with patch(
                    "backend.workers.tasks.mind_map_task.MindMapGenerator",
                    _make_mock_generator(),
                ):
                    mind_map_task(task_id, summary_task_id)

        cached_keys = [call.args[0] for call in mock_redis.setex.call_args_list]
        assert f"task:mind:result:{task_id}" in cached_keys


class TestMindMapTaskFailures:
    def test_task_fails_when_summary_result_missing(self):
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = "missing-summary"
        mock_redis = _make_mock_redis(summary_task_id, None)

        with patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.mind_map_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"
                result = mind_map_task(task_id, summary_task_id)

        assert result["status"] == "failed"
        assert "요약 결과를 찾을 수 없습니다" in result["error_message"]

    def test_task_fails_when_openai_key_missing(self):
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = "summary-task-1"
        mock_redis = _make_mock_redis(summary_task_id, MOCK_SUMMARY_RESULT)

        with patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.mind_map_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.openai_api_key = ""
                result = mind_map_task(task_id, summary_task_id)

        assert result["status"] == "failed"
        assert result["error_message"] == "OPENAI_API_KEY is not configured"
