"""
transcription_task 단위 테스트
REQ-STT-005, 008, 009, 013, 018: STT 워커 내부 함수 검증
TDD RED → GREEN cycle
"""

import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.schemas.transcription import SegmentResult, TaskStatus

# ---------------------------------------------------------------------------
# _extract_segments 테스트 (순수 함수)
# ---------------------------------------------------------------------------


class TestExtractSegments:
    """REQ-STT-008: 세그먼트별 텍스트, 시작/종료 시간, 신뢰도 추출"""

    def test_extracts_valid_segments(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [
            {"start": 0.0, "end": 4.2, "text": "안녕하세요.", "avg_logprob": -0.25},
            {"start": 4.5, "end": 8.1, "text": "반갑습니다.", "avg_logprob": -0.30},
        ]
        result = _extract_segments(raw)

        assert len(result) == 2
        assert result[0].text == "안녕하세요."
        assert result[0].start == 0.0
        assert result[0].end == 4.2
        assert result[1].text == "반갑습니다."

    def test_skips_empty_text_segments(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [
            {"start": 0.0, "end": 1.0, "text": "유효한 텍스트", "avg_logprob": -0.2},
            {"start": 1.0, "end": 2.0, "text": "", "avg_logprob": -0.5},
            {"start": 2.0, "end": 3.0, "text": "   ", "avg_logprob": -0.3},
        ]
        result = _extract_segments(raw)
        assert len(result) == 1
        assert result[0].text == "유효한 텍스트"

    def test_confidence_from_avg_logprob(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [{"start": 0.0, "end": 1.0, "text": "테스트", "avg_logprob": -0.25}]
        result = _extract_segments(raw)

        expected_confidence = min(1.0, max(0.0, math.exp(-0.25)))
        assert result[0].confidence == round(expected_confidence, 4)

    def test_confidence_zero_when_no_logprob(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [{"start": 0.0, "end": 1.0, "text": "테스트"}]
        result = _extract_segments(raw)
        assert result[0].confidence == 0.0

    def test_confidence_clamped_to_max_1(self):
        """avg_logprob가 양수일 때 confidence는 1.0으로 클램핑"""
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [{"start": 0.0, "end": 1.0, "text": "테스트", "avg_logprob": 1.0}]
        result = _extract_segments(raw)
        assert result[0].confidence == 1.0

    def test_empty_input_returns_empty_list(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        assert _extract_segments([]) == []

    def test_returns_segment_result_instances(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [{"start": 0.0, "end": 1.0, "text": "테스트", "avg_logprob": -0.5}]
        result = _extract_segments(raw)
        assert isinstance(result[0], SegmentResult)

    def test_segment_ids_are_sequential(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [
            {"start": 0.0, "end": 1.0, "text": "첫 번째", "avg_logprob": -0.2},
            {"start": 1.0, "end": 2.0, "text": "두 번째", "avg_logprob": -0.3},
            {"start": 2.0, "end": 3.0, "text": "세 번째", "avg_logprob": -0.4},
        ]
        result = _extract_segments(raw)
        assert [s.id for s in result] == [0, 1, 2]

    def test_timestamps_are_rounded(self):
        from backend.workers.tasks.transcription_task import _extract_segments

        raw = [{"start": 0.123456789, "end": 1.987654321, "text": "테스트", "avg_logprob": -0.2}]
        result = _extract_segments(raw)
        assert result[0].start == 0.123
        assert result[0].end == 1.988


# ---------------------------------------------------------------------------
# _update_task_status 테스트
# ---------------------------------------------------------------------------


class TestUpdateTaskStatus:
    """Redis에 작업 상태 저장 검증"""

    @patch("backend.workers.tasks.transcription_task._get_redis")
    @patch("backend.workers.tasks.transcription_task.publish_task_event_sync")
    def test_stores_status_in_redis(self, mock_pubsub, mock_get_redis):
        from backend.workers.tasks.transcription_task import _update_task_status

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None]  # 기존 상태 없음
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        _update_task_status("test-task-id", TaskStatus.processing, 0.5, "처리 중...")

        # pipe.setex 호출 확인
        mock_pipe.setex.assert_called()
        call_args = mock_pipe.setex.call_args
        key = call_args[0][0]
        assert key == "task:status:test-task-id"

        stored_data = json.loads(call_args[0][2])
        assert stored_data["task_id"] == "test-task-id"
        assert stored_data["status"] == "processing"
        assert stored_data["progress"] == 0.5
        assert stored_data["message"] == "처리 중..."

    @patch("backend.workers.tasks.transcription_task._get_redis")
    @patch("backend.workers.tasks.transcription_task.publish_task_event_sync")
    def test_stores_error_message(self, mock_pubsub, mock_get_redis):
        from backend.workers.tasks.transcription_task import _update_task_status

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None]  # 기존 상태 없음
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        _update_task_status(
            "test-id",
            TaskStatus.failed,
            0.0,
            error_message="파일 손상",
        )

        stored_data = json.loads(mock_pipe.setex.call_args[0][2])
        assert stored_data["error_message"] == "파일 손상"
        assert stored_data["status"] == "failed"

    @patch("backend.workers.tasks.transcription_task._get_redis")
    @patch("backend.workers.tasks.transcription_task.publish_task_event_sync")
    def test_omits_optional_fields_when_none(self, mock_pubsub, mock_get_redis):
        from backend.workers.tasks.transcription_task import _update_task_status

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [None]  # 기존 상태 없음
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        _update_task_status("test-id", TaskStatus.pending)

        stored_data = json.loads(mock_redis.setex.call_args[0][2])
        assert "message" not in stored_data
        assert "error_message" not in stored_data


# ---------------------------------------------------------------------------
# _cache_result 테스트
# ---------------------------------------------------------------------------


class TestCacheResult:
    """REQ-STT-013: 24h TTL Redis 캐싱 검증"""

    @patch("backend.workers.tasks.transcription_task._get_redis")
    def test_stores_result_with_ttl(self, mock_get_redis):
        from backend.workers.tasks.transcription_task import _cache_result

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        result = {"task_id": "abc", "status": "completed", "segments": []}
        _cache_result("abc", result)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0] == "task:result:abc"
        assert json.loads(call_args[2]) == result


# ---------------------------------------------------------------------------
# _get_active_job_count / _increment / _decrement 테스트
# ---------------------------------------------------------------------------


class TestActiveJobTracking:
    """동시 처리 수 추적 검증"""

    @patch("backend.workers.tasks.transcription_task._get_redis")
    def test_get_count_returns_zero_when_none(self, mock_get_redis):
        from backend.workers.tasks.transcription_task import _get_active_job_count

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis

        assert _get_active_job_count() == 0

    @patch("backend.workers.tasks.transcription_task._get_redis")
    def test_get_count_returns_integer(self, mock_get_redis):
        from backend.workers.tasks.transcription_task import _get_active_job_count

        mock_redis = MagicMock()
        mock_redis.get.return_value = "2"
        mock_get_redis.return_value = mock_redis

        assert _get_active_job_count() == 2

    @patch("backend.workers.tasks.transcription_task._get_redis")
    def test_increment_uses_pipeline(self, mock_get_redis):
        from backend.workers.tasks.transcription_task import _increment_active_jobs

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        _increment_active_jobs("task-123")

        mock_pipe.incr.assert_called_once_with("active_job_count")
        mock_pipe.sadd.assert_called_once_with("active_jobs", "task-123")
        mock_pipe.execute.assert_called_once()

    @patch("backend.workers.tasks.transcription_task._get_redis")
    def test_decrement_uses_pipeline(self, mock_get_redis):
        from backend.workers.tasks.transcription_task import _decrement_active_jobs

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_redis.return_value = mock_redis

        _decrement_active_jobs("task-123")

        mock_pipe.decr.assert_called_once_with("active_job_count")
        mock_pipe.srem.assert_called_once_with("active_jobs", "task-123")
        mock_pipe.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _process_chunks 테스트
# ---------------------------------------------------------------------------


class TestProcessChunks:
    """REQ-STT-018: 청크별 처리 및 병합"""

    @patch("backend.workers.tasks.transcription_task._update_task_status")
    @patch("backend.workers.tasks.transcription_task.merge_segments")
    def test_processes_all_chunks(self, mock_merge, mock_status):
        from backend.workers.tasks.transcription_task import _process_chunks

        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {
            "segments": [{"start": 0.0, "end": 1.0, "text": "테스트"}]
        }

        chunk1 = MagicMock()
        chunk1.file_path = Path("/tmp/chunk_0.wav")
        chunk2 = MagicMock()
        chunk2.file_path = Path("/tmp/chunk_1.wav")
        chunks = [chunk1, chunk2]

        expected = [SegmentResult(id=0, start=0.0, end=1.0, text="테스트", confidence=0.5)]
        mock_merge.return_value = expected

        result = _process_chunks(mock_engine, chunks, "task-id", "ko")

        assert mock_engine.transcribe.call_count == 2
        mock_merge.assert_called_once()
        assert result == expected

    @patch("backend.workers.tasks.transcription_task._update_task_status")
    @patch("backend.workers.tasks.transcription_task.merge_segments")
    def test_updates_progress_per_chunk(self, mock_merge, mock_status):
        from backend.workers.tasks.transcription_task import _process_chunks

        mock_engine = MagicMock()
        mock_engine.transcribe.return_value = {"segments": []}
        mock_merge.return_value = []

        chunks = [MagicMock() for _ in range(3)]
        for i, c in enumerate(chunks):
            c.file_path = Path(f"/tmp/chunk_{i}.wav")

        _process_chunks(mock_engine, chunks, "task-id", "ko")

        assert mock_status.call_count == 3
        # 각 호출에서 progress 메시지에 청크 번호 포함 확인
        for i, call in enumerate(mock_status.call_args_list):
            msg = call[0][3]  # 4번째 positional arg = message
            assert f"청크 {i + 1}/3" in msg


# ---------------------------------------------------------------------------
# transcription_task 메인 함수 통합 테스트 (mock 기반)
# ---------------------------------------------------------------------------


class TestTranscriptionTaskMain:
    """transcription_task Celery 작업 메인 흐름 검증"""

    @patch("backend.workers.tasks.transcription_task.cleanup_temp_file")
    @patch("backend.workers.tasks.transcription_task._decrement_active_jobs")
    @patch("backend.workers.tasks.transcription_task._increment_active_jobs")
    @patch("backend.workers.tasks.transcription_task._cache_result")
    @patch("backend.workers.tasks.transcription_task._update_task_status")
    @patch("backend.workers.tasks.transcription_task.split_audio")
    @patch("backend.workers.tasks.transcription_task.get_audio_duration_seconds")
    @patch("backend.workers.tasks.transcription_task.convert_and_normalize")
    @patch("backend.workers.tasks.transcription_task.WhisperEngine")
    @patch("backend.workers.tasks.transcription_task.settings")
    def test_successful_short_audio(
        self,
        mock_settings,
        mock_engine_cls,
        mock_convert,
        mock_duration,
        mock_split,
        mock_status,
        mock_cache,
        mock_incr,
        mock_decr,
        mock_cleanup,
        tmp_path,
    ):
        """30분 이하 오디오 정상 처리 흐름"""
        mock_settings.results_dir = tmp_path
        mock_settings.cache_ttl_seconds = 604800
        mock_settings.chunk_duration_ms = 1800000
        mock_settings.chunk_overlap_ms = 5000

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")

        processed = tmp_path / "processed.wav"
        processed.write_bytes(b"processed")
        mock_convert.return_value = processed
        mock_duration.return_value = 60.0
        mock_split.return_value = []

        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.transcribe.return_value = {
            "segments": [{"start": 0.0, "end": 4.2, "text": "안녕하세요.", "avg_logprob": -0.25}]
        }
        mock_engine_cls.get_instance.return_value = mock_engine

        from backend.workers.tasks.transcription_task import transcription_task

        # Celery eager 모드로 실행 (bind=True이므로 self 자동 주입)
        result = transcription_task.apply(
            args=(),
            kwargs={
                "task_id": "test-task-001",
                "audio_file_path": str(audio_file),
                "language": "ko",
                "original_filename": "meeting.wav",
                "file_size_bytes": 1000,
            },
        ).result

        assert result["task_id"] == "test-task-001"
        assert result["status"] == "completed"
        assert result["language"] == "ko"
        assert len(result["segments"]) == 1
        assert result["segments"][0]["text"] == "안녕하세요."
        assert result["metadata"]["file_name"] == "meeting.wav"

        mock_incr.assert_called_once_with("test-task-001")
        mock_decr.assert_called_once_with("test-task-001")
        mock_cache.assert_called_once()

    @patch("backend.workers.tasks.transcription_task.cleanup_temp_file")
    @patch("backend.workers.tasks.transcription_task._decrement_active_jobs")
    @patch("backend.workers.tasks.transcription_task._increment_active_jobs")
    @patch("backend.workers.tasks.transcription_task._cache_result")
    @patch("backend.workers.tasks.transcription_task._update_task_status")
    @patch("backend.workers.tasks.transcription_task.convert_and_normalize")
    @patch("backend.workers.tasks.transcription_task.settings")
    def test_file_not_found_marks_failed(
        self,
        mock_settings,
        mock_convert,
        mock_status,
        mock_cache,
        mock_incr,
        mock_decr,
        mock_cleanup,
        tmp_path,
    ):
        """REQ-STT-009: 파일 없을 때 failed 상태 + 캐시 저장"""
        mock_settings.results_dir = tmp_path

        from backend.workers.tasks.transcription_task import transcription_task

        # Celery eager 모드에서 retry는 예외를 다시 발생시킴
        # max_retries 초과 시 원래 예외가 전파됨
        try:
            transcription_task.apply(
                args=(),
                kwargs={
                    "task_id": "missing-file-task",
                    "audio_file_path": "/nonexistent/path/audio.wav",
                },
                throw=True,
            )
        except Exception:
            pass

        # failed 상태로 기록되었는지 확인
        mock_status.assert_called()
        # 마지막 상태 업데이트가 failed인지 확인
        last_status_call = mock_status.call_args_list[-1]
        assert last_status_call[0][1] == TaskStatus.failed

        # 실패 결과가 캐시에 저장되었는지 확인
        mock_cache.assert_called()
        cached_data = mock_cache.call_args[0][1]
        assert cached_data["status"] == "failed"

        mock_decr.assert_called_once()

    @patch("backend.workers.tasks.transcription_task.cleanup_temp_file")
    @patch("backend.workers.tasks.transcription_task._decrement_active_jobs")
    @patch("backend.workers.tasks.transcription_task._increment_active_jobs")
    @patch("backend.workers.tasks.transcription_task._cache_result")
    @patch("backend.workers.tasks.transcription_task._update_task_status")
    @patch("backend.workers.tasks.transcription_task.split_audio")
    @patch("backend.workers.tasks.transcription_task.get_audio_duration_seconds")
    @patch("backend.workers.tasks.transcription_task.convert_and_normalize")
    @patch("backend.workers.tasks.transcription_task.WhisperEngine")
    @patch("backend.workers.tasks.transcription_task.settings")
    def test_result_saved_to_filesystem(
        self,
        mock_settings,
        mock_engine_cls,
        mock_convert,
        mock_duration,
        mock_split,
        mock_status,
        mock_cache,
        mock_incr,
        mock_decr,
        mock_cleanup,
        tmp_path,
    ):
        """결과가 파일 시스템에도 저장되는지 확인"""
        mock_settings.results_dir = tmp_path
        mock_settings.cache_ttl_seconds = 604800
        mock_settings.chunk_duration_ms = 1800000
        mock_settings.chunk_overlap_ms = 5000

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        processed = tmp_path / "processed.wav"
        processed.write_bytes(b"processed")
        mock_convert.return_value = processed
        mock_duration.return_value = 30.0
        mock_split.return_value = []

        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.transcribe.return_value = {"segments": []}
        mock_engine_cls.get_instance.return_value = mock_engine

        from backend.workers.tasks.transcription_task import transcription_task

        transcription_task.apply(
            args=(),
            kwargs={
                "task_id": "fs-save-task",
                "audio_file_path": str(audio_file),
            },
        )

        result_file = tmp_path / "fs-save-task.json"
        assert result_file.exists()
        saved = json.loads(result_file.read_text())
        assert saved["task_id"] == "fs-save-task"
        assert saved["status"] == "completed"
