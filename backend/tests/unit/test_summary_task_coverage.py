"""
요약 태스크 추가 커버리지 테스트
커버되지 않는 라인: 49-50, 59, 219, 269-270, 305-306, 333-334
"""

import json
import uuid
from unittest.mock import MagicMock, patch


def _make_mock_redis(active_count: int = 0):
    """Redis 동기 클라이언트 mock 생성"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.zadd.return_value = 1
    mock.zrem.return_value = 1
    pipe = MagicMock()
    pipe.zremrangebyscore.return_value = 0
    pipe.zcard.return_value = active_count
    pipe.execute.return_value = [0, active_count]
    mock.pipeline.return_value = pipe
    return mock


# 정상 회의록 결과
MOCK_MIN_RESULT = {
    "task_id": str(uuid.uuid4()),
    "diarization_task_id": str(uuid.uuid4()),
    "status": "completed",
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "text": "안녕하세요.",
            "start": 0.0,
            "end": 5.0,
        }
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "total_speaking_time": 5.0,
            "segment_count": 1,
            "speaking_ratio": 100.0,
        }
    ],
}


class TestSummaryTaskCoverage:
    """커버리지 구멍 메우기 위한 추가 테스트"""

    def test_update_status_preserves_created_at(self):
        """Lines 49-50, 59: 기존 created_at 보존"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.summary_task import _update_task_status

        mock_redis = MagicMock()
        existing_data = {
            "task_id": "test-id",
            "status": "processing",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(existing_data)

        with (
            patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.summary_task.publish_task_event_sync"),
            patch("backend.workers.tasks.summary_task.settings") as mock_settings,
        ):
            mock_settings.summary_result_ttl = 86400

            _update_task_status("test-id", TaskStatus.processing, 0.5)

        saved_data = json.loads(mock_redis.setex.call_args[0][2])
        assert saved_data["created_at"] == "2024-01-01T00:00:00+00:00"

    def test_update_status_without_existing_created_at(self):
        """Line 59: 기존 상태 없을 때 created_at 없이 저장"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.summary_task import _update_task_status

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.summary_task.publish_task_event_sync"),
            patch("backend.workers.tasks.summary_task.settings") as mock_settings,
        ):
            mock_settings.summary_result_ttl = 86400

            _update_task_status("test-id", TaskStatus.processing, 0.5)

        saved_data = json.loads(mock_redis.setex.call_args[0][2])
        assert "created_at" not in saved_data

    def test_cache_result_with_ttl(self):
        """Line 219: 결과 Redis 캐싱 시 summary_result_ttl 사용"""
        from backend.workers.tasks.summary_task import _cache_result

        mock_redis = MagicMock()

        with (
            patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.summary_task.settings") as mock_settings,
        ):
            mock_settings.summary_result_ttl = 86400

            result = {"task_id": "test-id", "status": "completed"}
            _cache_result("test-id", result)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 86400  # TTL 확인

    def test_failed_propagates_error_message(self):
        """Line 269-270: 실패 시 error_message 저장"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = MagicMock()
        mock_gen_cls.return_value.generate_summary.side_effect = Exception("API error")

        with (
            patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.summary_task.settings") as mock_settings,
            patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls),
        ):
            mock_settings.summary_result_ttl = 86400
            mock_settings.max_concurrent_summaries = 2
            mock_settings.openai_api_key = "sk-test"
            mock_settings.summary_model = "gpt-4o-mini"

            result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] == "failed"
        assert "error" in result or "error_message" in result

    def test_active_job_registration(self):
        """Lines 305-306: 활성 작업 등록/해제"""
        from backend.workers.tasks.summary_task import _register_active_job, _unregister_active_job

        mock_redis = MagicMock()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            _register_active_job("task-id")

        mock_redis.zadd.assert_called_once()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            _unregister_active_job("task-id")

        mock_redis.zrem.assert_called_once_with("active_sum_jobs_ts", "task-id")

    def test_get_active_count_with_cleanup(self):
        """Lines 333-334: 활성 작업 수 조회 시 고아 항목 정리"""
        from backend.workers.tasks.summary_task import _get_active_sum_count

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore.return_value = 5  # 5개 정리됨
        mock_pipe.zcard.return_value = 3  # 3개 활성 중
        mock_pipe.execute.return_value = [5, 3]
        mock_redis.pipeline.return_value = mock_pipe

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            count = _get_active_sum_count()

        assert count == 3
        mock_pipe.zremrangebyscore.assert_called_once()
        mock_pipe.zcard.assert_called_once_with("active_sum_jobs_ts")
