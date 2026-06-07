"""
감정 분석 태스크 추가 커버리지 테스트
커버되지 않는 라인: 25, 203-204
"""

import json
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
    "task_id": "test-minutes-id",
    "status": "completed",
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "text": "좋은 방향입니다.",
            "start": 0.0,
            "end": 4.0,
        }
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "total_speaking_time": 4.0,
            "segment_count": 1,
            "speaking_ratio": 100.0,
        }
    ],
}


class TestSentimentTaskCoverage:
    """커버리지 구멍 메우기 위한 추가 테스트"""

    def test_get_redis_returns_worker_redis(self):
        """Line 25: _get_redis() 함수가 get_worker_redis()를 호출"""
        from backend.workers.tasks.sentiment_task import _get_redis

        mock_client = MagicMock()
        with patch(
            "backend.workers.tasks.sentiment_task.get_worker_redis", return_value=mock_client
        ):
            result = _get_redis()

        assert result is mock_client

    def test_failed_task_caches_error_message(self):
        """Lines 203-204: 실패 시 error_message 저장"""
        from backend.workers.tasks.sentiment_task import sentiment_task

        task_id = "test-sentiment-id"
        minutes_task_id = "test-minutes-id"

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{minutes_task_id}" in key else None
        )

        mock_analyzer_cls = MagicMock()
        mock_analyzer_cls.return_value.analyze.side_effect = Exception("Analysis failed")

        with (
            patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.sentiment_task.settings") as mock_settings,
            patch("backend.workers.tasks.sentiment_task.SentimentAnalyzer", mock_analyzer_cls),
        ):
            mock_settings.summary_result_ttl = 86400
            mock_settings.openai_api_key = "sk-test"
            mock_settings.summary_model = "gpt-4o-mini"

            result = sentiment_task(task_id=task_id, minutes_task_id=minutes_task_id)

        assert result["status"] == "failed"
        assert "error" in result or "error_message" in result
