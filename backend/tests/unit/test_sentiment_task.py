"""
sentiment_task 단위 테스트
SPEC-SENTIMENT-001: 회의록 기반 감정 분석 Celery 태스크
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from backend.schemas.sentiment import (
    SentimentResult,
    SentimentSegment,
    SpeakerSentiment,
)

MOCK_MIN_RESULT = {
    "task_id": str(uuid.uuid4()),
    "diarization_task_id": str(uuid.uuid4()),
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


def _make_mock_redis(active_count: int = 0) -> MagicMock:
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


def _make_sentiment_result() -> SentimentResult:
    """감정 분석기 mock이 반환할 결과"""
    segment = SentimentSegment(
        start=0.0,
        end=4.0,
        speaker="Speaker 1",
        text="좋은 방향입니다.",
        sentiment="positive",
        emotion="satisfaction",
        confidence=0.91,
    )
    speaker = SpeakerSentiment(
        speaker="Speaker 1",
        total_segments=1,
        positive_ratio=1.0,
        neutral_ratio=0.0,
        negative_ratio=0.0,
        dominant_emotion="satisfaction",
        emotion_distribution={"satisfaction": 1},
    )
    return SentimentResult(
        overall_sentiment="positive",
        overall_emotion="satisfaction",
        segments=[segment],
        speakers=[speaker],
        emotional_timeline=[
            {
                "time": 0.0,
                "sentiment": "positive",
                "emotion": "satisfaction",
                "speaker": "Speaker 1",
            }
        ],
    )


def _configure_settings(mock_settings: MagicMock) -> None:
    mock_settings.summary_result_ttl = 86400
    mock_settings.openai_api_key = "sk-test-key"
    mock_settings.summary_model = "gpt-4o-mini"


class TestSentimentTaskHappyPath:
    """정상 감정 분석 흐름 테스트"""

    def test_task_returns_completed_result(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        task_id = str(uuid.uuid4())
        minutes_task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{minutes_task_id}" in key else None
        )
        analyzer_cls = MagicMock()
        analyzer_cls.return_value.analyze.return_value = _make_sentiment_result()

        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings, \
             patch("backend.workers.tasks.sentiment_task.SentimentAnalyzer", analyzer_cls):
            _configure_settings(mock_settings)

            result = sentiment_task(
                task_id=task_id,
                minutes_task_id=minutes_task_id,
                max_tokens=1024,
            )

        assert result["status"] == "completed"
        assert result["task_id"] == task_id
        assert result["minutes_task_id"] == minutes_task_id
        assert result["overall_sentiment"] == "positive"
        assert result["segments"][0]["emotion"] == "satisfaction"
        analyzer_cls.return_value.analyze.assert_called_once_with(
            segments=MOCK_MIN_RESULT["segments"],
            speaker_stats=MOCK_MIN_RESULT["speakers"],
            api_key="sk-test-key",
            model="gpt-4o-mini",
            max_tokens=1024,
        )

    def test_task_caches_completed_result(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        task_id = str(uuid.uuid4())
        minutes_task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{minutes_task_id}" in key else None
        )
        analyzer_cls = MagicMock()
        analyzer_cls.return_value.analyze.return_value = _make_sentiment_result()

        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings, \
             patch("backend.workers.tasks.sentiment_task.SentimentAnalyzer", analyzer_cls):
            _configure_settings(mock_settings)
            sentiment_task(task_id=task_id, minutes_task_id=minutes_task_id)

        result_writes = [
            call for call in mock_redis.setex.call_args_list
            if call.args[0] == f"task:sentiment:result:{task_id}"
        ]
        assert result_writes
        cached_result = json.loads(result_writes[-1].args[2])
        assert cached_result["status"] == "completed"


class TestSentimentTaskErrors:
    """오류 조건 처리 테스트"""

    def test_empty_api_key_returns_failed_immediately(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        mock_redis = _make_mock_redis()
        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings:
            _configure_settings(mock_settings)
            mock_settings.openai_api_key = ""

            result = sentiment_task(task_id="task-id", minutes_task_id="minutes-id")

        assert result["status"] == "failed"
        assert "OPENAI_API_KEY" in result["error"]

    def test_max_concurrent_limit_returns_rejected(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        mock_redis = _make_mock_redis(active_count=3)
        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings:
            _configure_settings(mock_settings)

            result = sentiment_task(task_id="task-id", minutes_task_id="minutes-id")

        assert result["status"] == "rejected"
        assert "한도" in result["error_message"]

    def test_minutes_result_not_found_returns_failed(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None
        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings:
            _configure_settings(mock_settings)

            result = sentiment_task(task_id="task-id", minutes_task_id="missing-minutes")

        assert result["status"] == "failed"
        assert "missing-minutes" in result["error"]

    def test_failed_minutes_result_propagates_upstream_error(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        minutes_task_id = str(uuid.uuid4())
        failed_minutes = {
            "task_id": minutes_task_id,
            "status": "failed",
            "error_message": "회의록 생성 실패",
        }
        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(failed_minutes) if f"min:result:{minutes_task_id}" in key else None
        )

        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings:
            _configure_settings(mock_settings)

            result = sentiment_task(task_id="task-id", minutes_task_id=minutes_task_id)

        assert result["status"] == "failed"
        assert "회의록 생성 실패" in result["error_message"]

    def test_analyzer_exception_returns_failed(self):
        from backend.workers.tasks.sentiment_task import sentiment_task

        minutes_task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{minutes_task_id}" in key else None
        )
        analyzer_cls = MagicMock()
        analyzer_cls.return_value.analyze.side_effect = RuntimeError("OpenAI timeout")

        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings, \
             patch("backend.workers.tasks.sentiment_task.SentimentAnalyzer", analyzer_cls):
            _configure_settings(mock_settings)

            result = sentiment_task(task_id="task-id", minutes_task_id=minutes_task_id)

        assert result["status"] == "failed"
        assert "OpenAI timeout" in result["error"]


class TestSentimentTaskHelpers:
    """상태/동시성 helper 검증"""

    def test_update_task_status_preserves_created_at(self):
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.sentiment_task import _update_task_status

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = json.dumps({"created_at": "2026-01-01T00:00:00+00:00"})

        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.sentiment_task.publish_task_event_sync"), \
             patch("backend.workers.tasks.sentiment_task.settings") as mock_settings:
            mock_settings.summary_result_ttl = 86400
            _update_task_status("task-id", TaskStatus.processing, 0.25, "처리 중")

        stored = json.loads(mock_redis.setex.call_args.args[2])
        assert stored["created_at"] == "2026-01-01T00:00:00+00:00"
        assert stored["message"] == "처리 중"

    def test_active_count_uses_sorted_set_cleanup(self):
        from backend.workers.tasks.sentiment_task import _get_active_sentiment_count

        mock_redis = _make_mock_redis(active_count=2)
        with patch("backend.workers.tasks.sentiment_task._get_redis", return_value=mock_redis):
            assert _get_active_sentiment_count() == 2

        pipe = mock_redis.pipeline.return_value
        pipe.zremrangebyscore.assert_called_once()
        pipe.zcard.assert_called_once_with("active_sentiment_jobs_ts")


class TestSentimentCeleryWrapper:
    """Celery wrapper 분기 검증"""

    def test_wrapper_returns_failed_for_missing_minutes(self):
        from backend.workers.tasks.sentiment_task import sentiment_celery_task

        with patch(
            "backend.workers.tasks.sentiment_task.sentiment_task",
            side_effect=FileNotFoundError("missing minutes"),
        ):
            result = sentiment_celery_task.run("task-id", "minutes-id")

        assert result == {
            "task_id": "task-id",
            "status": "failed",
            "error": "missing minutes",
        }

    def test_wrapper_returns_failed_after_max_retries(self):
        from backend.workers.tasks.sentiment_task import sentiment_celery_task

        with patch(
            "backend.workers.tasks.sentiment_task.sentiment_task",
            side_effect=RuntimeError("temporary outage"),
        ), patch.object(
            sentiment_celery_task,
            "retry",
            side_effect=sentiment_celery_task.MaxRetriesExceededError(),
        ) as retry:
            result = sentiment_celery_task.run("task-id", "minutes-id")

        retry.assert_called_once()
        assert result["status"] == "failed"
        assert result["error"] == "temporary outage"
