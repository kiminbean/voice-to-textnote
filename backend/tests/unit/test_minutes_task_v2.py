"""
회의록 생성 Celery 태스크 추가 테스트 (커버리지 보완)
기존 test_minutes_task.py에서 커버하지 않는 경로 테스트
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------


def _make_mock_redis():
    """Redis 동기 클라이언트 mock"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.scard.return_value = 0
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    mock.zadd.return_value = 1
    mock.zcard.return_value = 0
    mock.zrem.return_value = 1
    mock.zremrangebyscore.return_value = 0
    pipe_mock = MagicMock()
    pipe_mock.incr.return_value = None
    pipe_mock.sadd.return_value = None
    pipe_mock.decr.return_value = None
    pipe_mock.srem.return_value = None
    pipe_mock.zremrangebyscore.return_value = None
    pipe_mock.zcard.return_value = 0
    pipe_mock.execute.return_value = [1, 0]  # zremrangebyscore 결과, zcard 결과
    mock.pipeline.return_value = pipe_mock
    return mock


def _make_mock_dia_result(matched=True):
    """화자 분리 결과 mock"""

    return {
        "task_id": str(uuid.uuid4()),
        "diarization_task_id": str(uuid.uuid4()),
        "status": "completed",
        "segments": [
            {
                "speaker_id": "SPEAKER_00",
                "start": 0.0,
                "end": 5.0,
                "text": "안녕하세요",
                "confidence": 0.9,
            },
            {
                "speaker_id": "SPEAKER_01",
                "start": 6.0,
                "end": 10.0,
                "text": "반갑습니다",
                "confidence": 0.85,
            },
        ],
        "speakers": [
            {
                "speaker_id": "SPEAKER_00",
                "total_speaking_time": 5.0,
                "segment_count": 1,
            }
        ],
        "num_speakers": 1,
        "matched": matched,
    }


def _make_mock_stt_result():
    """STT 결과 mock"""
    return {
        "task_id": str(uuid.uuid4()),
        "status": "completed",
        "segments": [
            {"id": 0, "start": 0.0, "end": 5.0, "text": "안녕하세요.", "confidence": 0.9},
            {"id": 1, "start": 6.0, "end": 10.0, "text": "반갑습니다.", "confidence": 0.85},
        ],
        "language": "ko",
        "duration": 10.0,
    }


# ---------------------------------------------------------------------------
# DB 영속 저장 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskDBPersistence:
    """DB 영속 저장 (best-effort) 테스트"""

    def test_db_persist_on_success(self, tmp_path: Path):
        """성공 시 DB에 결과 저장 시도 (실패해도 진행)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result()) if "dia:result" in key else None
        )

        persist_called = []

        def mock_persist(**kwargs):
            persist_called.append(kwargs)

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings, \
             patch("backend.services.sync_service.persist_task_result", side_effect=mock_persist):
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        assert result["status"] == "completed"
        assert len(persist_called) == 1
        assert persist_called[0]["task_type"] == "minutes"
        assert persist_called[0]["status"] == "completed"

    def test_db_persist_failure_ignored_on_success(self, tmp_path: Path):
        """DB 저장 실패 시 Redis 저장만으로 성공 처리"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result()) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings, \
             patch("backend.services.sync_service.persist_task_result", side_effect=Exception("DB 연결 실패")):
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        # DB 저장 실패해도 Redis에 저장되었으므로 성공
        assert result["status"] == "completed"

    def test_db_persist_on_file_not_found_failure(self, tmp_path: Path):
        """FileNotFoundError 실패 시에도 DB 저장 시도"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None  # DIA 결과 없음

        persist_called = []

        def mock_persist(**kwargs):
            persist_called.append(kwargs)

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings, \
             patch("backend.services.sync_service.persist_task_result", side_effect=mock_persist):
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        assert result["status"] == "failed"
        assert len(persist_called) == 1
        assert persist_called[0]["status"] == "failed"

    def test_db_persist_on_generic_exception(self, tmp_path: Path):
        """일반 Exception 실패 시에도 DB 저장 시도"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result()) if "dia:result" in key else None
        )

        persist_called = []

        def mock_persist(**kwargs):
            persist_called.append(kwargs)
            raise Exception("DB 저장 오류")

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings, \
             patch("backend.services.sync_service.persist_task_result", side_effect=mock_persist):
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        # DB 저장 실패해도 Redis에 저장되었으므로 성공
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# 활성 작업 등록/해제 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskActiveJobManagement:
    """활성 작업 등록/해제 테스트"""

    def test_active_job_registered_on_start(self):
        """작업 시작 시 활성 작업 등록됨"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result()) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        # zadd 호출 확인 (활성 작업 등록)
        assert mock_redis.zadd.called

    def test_active_job_unregistered_in_finally(self):
        """finally 블록에서 활성 작업 해제됨 (성공/실패 모두)"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result()) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            try:
                minutes_task(
                    task_id=task_id,
                    diarization_task_id=dia_task_id,
                    output_format="json",
                )
            except Exception:
                pass

        # 성공해도 zrem 호출 확인 (활성 작업 해제)
        assert mock_redis.zrem.called


# ---------------------------------------------------------------------------
# 병렬 모드 테스트
# ---------------------------------------------------------------------------


class TestMinutesTaskParallelMode:
    """병렬 모드 관련 테스트"""

    def test_parallel_mode_with_matched_false(self):
        """dia 결과가 matched=False이고 stt_task_id 제공 시 매칭 수행"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result(matched=False)) if "dia:result" in key else (
                json.dumps(_make_mock_stt_result()) if "result" in key else None
            )
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                stt_task_id=stt_task_id,
                output_format="json",
            )

        assert result["status"] == "completed"
        assert "segments" in result
        assert "speakers" in result

    def test_parallel_mode_requires_stt_task_id_when_matched_false(self):
        """matched=False일 때 stt_task_id 없으면 RuntimeError"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result(matched=False)) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                stt_task_id=None,  # matched=False인데 stt_task_id 없음
                output_format="json",
            )

        assert result["status"] == "failed"
        assert "stt_task_id" in result["error_message"]

    def test_parallel_mode_stt_not_found_fails(self):
        """병렬 모드에서 STT 결과 없음 → 실패"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result(matched=False)) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                stt_task_id=stt_task_id,
                output_format="json",
            )

        assert result["status"] == "failed"
        assert "STT 결과를 찾을 수 없습니다" in result["error_message"]


# ---------------------------------------------------------------------------
# 레거시 모드 엣지 케이스
# ---------------------------------------------------------------------------


class TestMinutesTaskLegacyModeEdgeCases:
    """레거시 모드 (matched=True) 엣지 케이스"""

    def test_legacy_mode_uses_already_matched_segments(self):
        """레거시 모드에서는 이미 매칭된 segments를 그대로 사용"""
        from backend.workers.tasks.minutes_task import minutes_task

        task_id = str(uuid.uuid4())
        dia_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(_make_mock_dia_result(matched=True)) if "dia:result" in key else None
        )

        with patch("backend.workers.tasks.minutes_task._get_redis", return_value=mock_redis), \
             patch("backend.workers.tasks.minutes_task.settings") as mock_settings:
            mock_settings.minutes_result_ttl = 86400
            mock_settings.max_concurrent_minutes = 3

            result = minutes_task(
                task_id=task_id,
                diarization_task_id=dia_task_id,
                output_format="json",
            )

        assert result["status"] == "completed"
        assert "segments" in result
        assert "speakers" in result
