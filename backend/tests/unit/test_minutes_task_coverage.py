"""
회의록 태스크 추가 커버리지 테스트
커버되지 않는 라인: 50-51, 60, 197-230, 281-282, 318-319, 346-347
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


# 정상 화자 분리 결과
MOCK_DIA_RESULT = {
    "task_id": str(uuid.uuid4()),
    "stt_task_id": str(uuid.uuid4()),
    "status": "completed",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 5.0,
            "text": "안녕하세요.",
            "confidence": 0.9,
            "speaker_id": "SPEAKER_00",
            "speaker_confidence": 0.95,
        }
    ],
    "speakers": [{"speaker_id": "SPEAKER_00", "total_speaking_time": 5.0, "segment_count": 1}],
    "num_speakers": 1,
}


class TestMinutesTaskCoverage:
    """커버리지 구멍 메우기 위한 추가 테스트"""

    def test_update_status_preserves_created_at(self):
        """Lines 50-51, 60: 기존 created_at 보존"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.minutes_task import _update_task_status

        mock_redis = MagicMock()
        existing_data = {
            "task_id": "test-id",
            "status": "processing",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(existing_data)

        with (
            patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.minutes_task.publish_task_event_sync"),
            patch("backend.workers.tasks.minutes_task.settings") as mock_settings,
        ):
            mock_settings.minutes_result_ttl = 86400

            _update_task_status("test-id", TaskStatus.processing, 0.5)

        saved_data = json.loads(mock_redis.setex.call_args[0][2])
        assert saved_data["created_at"] == "2024-01-01T00:00:00+00:00"

    def test_update_status_without_existing_created_at(self):
        """Line 60: 기존 상태 없을 때 created_at 없이 저장"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.minutes_task import _update_task_status

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.minutes_task.publish_task_event_sync"),
            patch("backend.workers.tasks.minutes_task.settings") as mock_settings,
        ):
            mock_settings.minutes_result_ttl = 86400

            _update_task_status("test-id", TaskStatus.processing, 0.5)

        saved_data = json.loads(mock_redis.setex.call_args[0][2])
        assert "created_at" not in saved_data

    def test_cache_result_with_ttl(self):
        """Line 219: 결과 Redis 캐싱 시 minutes_result_ttl 사용"""
        from backend.workers.tasks.minutes_task import _cache_result

        mock_redis = MagicMock()

        with (
            patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.minutes_task.settings") as mock_settings,
        ):
            mock_settings.minutes_result_ttl = 86400

            result = {"task_id": "test-id", "status": "completed"}
            _cache_result("test-id", result)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 86400  # TTL 확인

    def test_extract_cached_error_message(self):
        """Line 197-230: _extract_cached_error_message 함수 테스트"""
        from backend.workers.tasks.minutes_task import _extract_cached_error_message

        # 레거시 error 키
        result_legacy = {"error": "레거시 에러"}
        assert _extract_cached_error_message(result_legacy) == "레거시 에러"

        # 신규 error_message 키
        result_new = {"error_message": "신규 에러"}
        assert _extract_cached_error_message(result_new) == "신규 에러"

        # 둘 다 있으면 error_message 우선
        result_both = {"error": "old", "error_message": "new"}
        assert _extract_cached_error_message(result_both) == "new"

        # 없으면 None
        assert _extract_cached_error_message({}) is None

    def test_failed_upstream_error_propagation(self):
        """Lines 281-282: 업스트림 실패 에러 전파"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        failed_dia = {
            "task_id": dia_task_id,
            "status": "failed",
            "error_message": "화자 분리 실패",
        }

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(failed_dia) if f"dia:result:{dia_task_id}" in key else None
        )

        with (
            patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.minutes_task.settings") as mock_settings,
        ):
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
            )

        assert result["status"] == "failed"
        assert "화자 분리 실패" in result["error_message"]

    def test_active_job_registration(self):
        """Lines 318-319: 활성 작업 등록/해제"""
        from backend.workers.tasks.minutes_task import _register_active_job, _unregister_active_job

        mock_redis = MagicMock()

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            _register_active_job("task-id")

        mock_redis.zadd.assert_called_once()

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            _unregister_active_job("task-id")

        mock_redis.zrem.assert_called_once_with("active_min_jobs_ts", "task-id")

    def test_get_active_count_with_cleanup(self):
        """Lines 346-347: 활성 작업 수 조회 시 고아 항목 정리"""
        from backend.workers.tasks.minutes_task import _get_active_min_count

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.zremrangebyscore.return_value = 5  # 5개 정리됨
        mock_pipe.zcard.return_value = 3  # 3개 활성 중
        mock_pipe.execute.return_value = [5, 3]
        mock_redis.pipeline.return_value = mock_pipe

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            count = _get_active_min_count()

        assert count == 3
        mock_pipe.zremrangebyscore.assert_called_once()
        mock_pipe.zcard.assert_called_once_with("active_min_jobs_ts")
