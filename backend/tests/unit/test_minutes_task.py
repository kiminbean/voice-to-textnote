"""
회의록 Celery 태스크 단위 테스트 (RED phase)
REQ-MIN-006~010: 비동기 회의록 생성 처리 워커
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from backend.workers.tasks.minutes_task import _get_redis

# ---------------------------------------------------------------------------
# 테스트 헬퍼 / 모의 데이터
# ---------------------------------------------------------------------------

# 정상 화자 분리 결과 (Redis에서 조회되는 형태)
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
        },
        {
            "id": 1,
            "start": 5.0,
            "end": 10.0,
            "text": "반갑습니다.",
            "confidence": 0.88,
            "speaker_id": "SPEAKER_01",
            "speaker_confidence": 0.92,
        },
    ],
    "speakers": [
        {"speaker_id": "SPEAKER_00", "total_speaking_time": 5.0, "segment_count": 1},
        {"speaker_id": "SPEAKER_01", "total_speaking_time": 5.0, "segment_count": 1},
    ],
    "num_speakers": 2,
    "created_at": "2025-01-01T00:00:00+00:00",
    "completed_at": "2025-01-01T00:00:10+00:00",
}


def _make_mock_redis(active_count: int = 0) -> MagicMock:
    """Redis 동기 클라이언트 mock 생성"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.scard.return_value = active_count
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    # _get_active_min_count() uses pipeline() → zremrangebyscore, zcard, execute
    mock_pipe = MagicMock()
    mock_pipe.zremrangebyscore.return_value = 0
    mock_pipe.zcard.return_value = active_count
    mock_pipe.zadd.return_value = 1
    mock_pipe.zrem.return_value = 1
    mock_pipe.execute.return_value = [0, active_count]
    mock.pipeline.return_value = mock_pipe
    return mock


# ---------------------------------------------------------------------------
# 정상 처리 흐름 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskHappyPath:
    """정상 회의록 생성 흐름 테스트"""

    def test_task_returns_completed_result(self):
        """화자 분리 결과 존재 → completed 결과 반환"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis(active_count=0)
        # 화자 분리 결과 반환 설정
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                    output_format="json",
                    speaker_names=None,
                )

        assert result["status"] == "completed"
        assert result["task_id"] == task_id
        assert result["diarization_task_id"] == dia_task_id

    def test_task_result_has_segments(self):
        """완료 결과에 segments 포함"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                )

        assert "segments" in result
        assert len(result["segments"]) >= 1

    def test_task_result_has_speakers(self):
        """완료 결과에 speakers 통계 포함"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                )

        assert "speakers" in result
        assert len(result["speakers"]) >= 1

    def test_task_caches_result_in_redis(self):
        """완료 후 결과가 Redis에 캐싱됨 (REQ-MIN-013: 24h TTL)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                minutes_task(task_id=task_id, diarization_task_id=dia_task_id)

        # Redis setex 호출 확인 (캐싱)
        assert mock_redis.setex.called

    def test_task_with_markdown_format(self):
        """output_format=markdown → markdown 필드 포함"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                    output_format="markdown",
                )

        assert result.get("markdown") is not None
        assert "**[" in result["markdown"]

    def test_task_with_custom_speaker_names(self):
        """speaker_names 매핑 적용 (REQ-MIN-017)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                    speaker_names={"SPEAKER_00": "김팀장"},
                )

        # 결과 segments에 화자 이름 반영 확인
        speaker_names_in_result = [seg["speaker_name"] for seg in result["segments"]]
        assert "김팀장" in speaker_names_in_result


# ---------------------------------------------------------------------------
# 오류 조건 처리 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskErrors:
    """오류 조건 처리 테스트"""

    def test_diarization_not_found_returns_failed(self):
        """화자 분리 결과 없음 → failed 반환 (REQ-MIN-010: 재시도 없음)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None  # 화자 분리 결과 없음

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                )

        assert result["status"] == "failed"
        assert "error" in result

    def test_max_concurrent_limit_returns_rejected(self):
        """동시 실행 3개 한도 초과 → rejected 반환 (REQ-MIN-008)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        # 이미 3개 활성 작업 중
        mock_redis = _make_mock_redis(active_count=3)
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                )

        assert result["status"] in ("failed", "rejected")

    def test_general_exception_returns_failed(self):
        """일반 예외 발생 → failed 상태"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        # json.loads가 실패하도록 유효하지 않은 JSON 반환
        mock_redis.get.side_effect = lambda key: (
            "invalid-json" if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                )

        assert result["status"] == "failed"

    def test_failed_diarization_result_propagates_upstream_error(self):
        """선행 화자 분리 실패 시 원인 메시지를 보존"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())
        failed_dia = {
            "task_id": dia_task_id,
            "status": "failed",
            "error_message": "STT 작업 실패",
        }

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(failed_dia) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(task_id=task_id, diarization_task_id=dia_task_id)

        assert result["status"] == "failed"
        assert "STT 작업 실패" in result["error_message"]


# ---------------------------------------------------------------------------
# 상태 전환 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskRedisClient:
    """_get_redis() 싱글톤 동작 테스트"""

    def test_get_redis_creates_client_when_none(self):
        """_get_redis()가 get_worker_redis()를 호출해 클라이언트 반환"""
        mock_client = MagicMock()
        with patch("backend.workers.tasks.minutes_task.get_worker_redis", return_value=mock_client):
            result = _get_redis()
        assert result is mock_client

    def test_get_redis_returns_cached_client(self):
        """_get_redis()가 항상 get_worker_redis() 결과를 반환"""
        mock_client = MagicMock()
        with patch("backend.workers.tasks.minutes_task.get_worker_redis", return_value=mock_client):
            result = _get_redis()
        assert result is mock_client


class TestMinutesTaskStatusTransitions:
    """상태 전환: pending → processing → completed/failed"""

    def test_status_updated_during_processing(self):
        """처리 중 status 업데이트 발생"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        status_updates = []

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        def track_setex(key, ttl, data):
            if "status" in key:
                try:
                    status_updates.append(json.loads(data))
                except Exception:
                    pass
            return True

        mock_redis.setex.side_effect = track_setex

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                minutes_task(task_id=task_id, diarization_task_id=dia_task_id)

        # processing 또는 completed 상태 업데이트 확인
        statuses = [u.get("status") for u in status_updates if "status" in u]
        assert any(s in ("processing", "completed") for s in statuses)

    def test_final_status_is_completed_on_success(self):
        """성공 시 최종 status=completed"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(task_id=task_id, diarization_task_id=dia_task_id)

        assert result["status"] == "completed"

    def test_result_has_required_fields(self):
        """완료 결과에 필수 필드 포함"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_DIA_RESULT) if f"dia:result:{dia_task_id}" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
                mock_settings.minutes_result_ttl = 86400
                mock_settings.max_concurrent_minutes = 3

                result = minutes_task(task_id=task_id, diarization_task_id=dia_task_id)

        for field in ("task_id", "diarization_task_id", "status", "segments", "speakers"):
            assert field in result, f"결과에 '{field}' 필드 누락"


class TestMinutesCeleryWrapper:
    """minutes_celery_task wrapper 분기 검증"""

    def test_wrapper_returns_failed_for_missing_diarization(self):
        from backend.workers.tasks.minutes_task import minutes_celery_task

        with patch(
            "backend.workers.tasks.minutes_task.minutes_task",
            side_effect=FileNotFoundError("missing diarization"),
        ):
            result = minutes_celery_task.run("task-id", "dia-id")

        assert result == {
            "task_id": "task-id",
            "status": "failed",
            "error": "missing diarization",
        }

    def test_wrapper_returns_failed_after_max_retries(self):
        from backend.workers.tasks.minutes_task import minutes_celery_task

        with (
            patch(
                "backend.workers.tasks.minutes_task.minutes_task",
                side_effect=RuntimeError("temporary outage"),
            ),
            patch.object(
                minutes_celery_task,
                "retry",
                side_effect=minutes_celery_task.MaxRetriesExceededError(),
            ) as retry,
        ):
            result = minutes_celery_task.run("task-id", "dia-id")

        retry.assert_called_once_with(exc=retry.call_args.kwargs["exc"], countdown=30)
        assert result["status"] == "failed"
        assert result["error"] == "temporary outage"
