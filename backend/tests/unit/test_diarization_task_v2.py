"""
화자 분리 Celery 태스크 추가 테스트 (커버리지 보완)
기존 test_diarization_task.py에서 커버하지 않는 경로 테스트
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.schemas.transcription import TaskStatus


def _make_mock_redis():
    """Redis 동기 클라이언트 mock"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = 1
    pipe_mock = MagicMock()
    pipe_mock.execute.return_value = [0, 0]
    mock.pipeline.return_value = pipe_mock
    return mock


def _make_mock_engine():
    """DiarizationEngine mock"""
    from backend.pipeline.speaker_matcher import SpeakerSegment

    mock_engine = MagicMock()
    mock_engine.is_loaded = True
    mock_engine.diarize.return_value = [
        SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
        SpeakerSegment(speaker_id="SPEAKER_01", start=6.0, end=10.0),
    ]
    return mock_engine


def _default_settings(tmp_path):
    """공통 settings mock"""
    s = MagicMock()
    s.temp_dir = tmp_path
    s.diarization_result_ttl = 86400
    s.max_concurrent_diarizations = 2
    s.huggingface_token = "hf_test"
    s.diarization_model = "test-model"
    s.dia_chunk_threshold_minutes = 15
    s.dia_chunk_duration_minutes = 10
    s.dia_chunk_overlap_seconds = 5
    s.dia_target_sample_rate = 0
    # SPEC-TONE-001: tone_model 기본값은 빈 문자열 (기능 비활성화)
    s.tone_model = ""
    return s


# ---------------------------------------------------------------------------
# created_at 보존 테스트 (lines 50-51, 60)
# ---------------------------------------------------------------------------


class TestDiarizationStatusPreservation:
    """_update_task_status created_at 보존 로직 테스트"""

    def test_preserves_existing_created_at(self):
        """기존 created_at이 있으면 상태 업데이트 시 보존"""
        from backend.workers.tasks.diarization_task import _update_task_status

        task_id = str(uuid.uuid4())

        existing_data = {
            "task_id": task_id,
            "status": "processing",
            "created_at": "2024-01-01T00:00:00+00:00",
        }

        mock_redis = _make_mock_redis()
        # status 키 조회 시 기존 데이터 반환
        mock_redis.get.side_effect = lambda key: (
            json.dumps(existing_data) if "status" in key else None
        )

        mock_settings = MagicMock()
        mock_settings.diarization_result_ttl = 86400

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
        ):
            _update_task_status(task_id, TaskStatus.processing, 0.5)

        # setex 호출 확인 - data에 created_at 보존
        call_args = mock_redis.setex.call_args
        saved_data = json.loads(call_args[0][2])
        assert saved_data["created_at"] == "2024-01-01T00:00:00+00:00"

    def test_no_created_at_when_no_existing_status(self):
        """기존 상태가 없으면 created_at 없음"""
        from backend.workers.tasks.diarization_task import _update_task_status

        task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None  # 기존 상태 없음

        mock_settings = MagicMock()
        mock_settings.diarization_result_ttl = 86400

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
        ):
            _update_task_status(task_id, TaskStatus.processing, 0.1)

        call_args = mock_redis.setex.call_args
        saved_data = json.loads(call_args[0][2])
        assert "created_at" not in saved_data


# ---------------------------------------------------------------------------
# 동시 작업 한도 초과 테스트 (lines 155-170)
# ---------------------------------------------------------------------------


class TestDiarizationConcurrencyLimit:
    """동시 작업 한도 초과 시 rejected 결과 테스트"""

    def test_rejected_result_has_all_fields(self, tmp_path: Path):
        """한도 초과 시 rejected 결과에 필수 필드 포함"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        # pipeline execute가 2개 활성 작업 반환
        mock_redis.pipeline.return_value.execute.return_value = [0, 2]

        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
        ):
            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "rejected"
        assert result["task_id"] == task_id
        assert result["stt_task_id"] == stt_task_id
        assert "한도" in result["error_message"]


# ---------------------------------------------------------------------------
# 레거시 모드 stt_task_id 누락 테스트 (line 188)
# ---------------------------------------------------------------------------


class TestDiarizationLegacyModeErrors:
    """레거시 모드 필수 파라미터 누락 테스트"""

    def test_legacy_mode_requires_stt_task_id(self, tmp_path: Path):
        """audio_path 없이 stt_task_id도 없으면 RuntimeError"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
        ):
            result = diarization_task(task_id=task_id)

        assert result["status"] == "failed"
        assert "stt_task_id" in result["error_message"]


# ---------------------------------------------------------------------------
# 병렬 모드 테스트 (lines 181-184, 270-286, 446-449)
# ---------------------------------------------------------------------------


class TestDiarizationParallelMode:
    """병렬 모드 (audio_path 제공) 테스트"""

    def test_parallel_mode_wav_not_found(self, tmp_path: Path):
        """병렬 모드에서 WAV 파일 없음 → FileNotFoundError"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        fake_wav = str(tmp_path / "nonexistent.wav")

        mock_redis = _make_mock_redis()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.workers.tasks.diarization_task.time.sleep"),
        ):
            result = diarization_task(
                task_id=task_id,
                audio_path=fake_wav,
            )

        assert result["status"] == "failed"
        assert "WAV 파일" in result["error_message"]

    def test_parallel_mode_raw_segments(self, tmp_path: Path):
        """병렬 모드 + STT 결과 없음 → raw segments 반환 (matched=False)"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_engine = _make_mock_engine()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine.get_instance",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            result = diarization_task(
                task_id=task_id,
                audio_path=str(wav_path),
            )

        assert result["status"] == "completed"
        assert result["matched"] is False
        assert len(result["segments"]) == 2
        assert "speakers" in result
        assert result["num_speakers"] == 2

    def test_parallel_mode_cleans_up_audio_file(self, tmp_path: Path):
        """병렬 모드 완료 후 오디오 파일 정리됨"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "cleanup_test.wav"
        wav_path.write_bytes(b"\x00" * 100)
        assert wav_path.exists()

        mock_redis = _make_mock_redis()
        mock_engine = _make_mock_engine()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine.get_instance",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            diarization_task(task_id=task_id, audio_path=str(wav_path))

        # finally 블록에서 파일 삭제됨 (line 446-449)
        assert not wav_path.exists()

    def test_parallel_mode_cleanup_ignores_os_error(self, tmp_path: Path):
        """파일 삭제 중 OSError 발생해도 예외 전파 안 함"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "oserr_test.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_engine = _make_mock_engine()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine.get_instance",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
            patch("backend.workers.tasks.diarization_task.Path") as mock_path_cls,
        ):
            # Path.unlink에서 OSError 발생
            mock_path_instance = MagicMock()
            mock_path_instance.unlink.side_effect = OSError("permission denied")
            mock_path_instance.exists.return_value = True
            mock_path_instance.__truediv__ = lambda s, o: mock_path_instance
            mock_path_cls.return_value = mock_path_instance

            # OSError가 발생해도 예외 전파되지 않음
            result = diarization_task(task_id=task_id, audio_path="/fake/path.wav")

        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# DB 영속 저장 예외 처리 테스트 (lines 351-352, 407-408, 435-436)
# ---------------------------------------------------------------------------


class TestDiarizationDbPersistErrors:
    """DB 영속 저장 실패 시 무시 (best-effort) 테스트"""

    def test_db_persist_failure_on_success_ignored(self, tmp_path: Path):
        """성공 경로에서 DB 저장 실패해도 결과 반환됨"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        (tmp_path / f"{stt_task_id}.wav").write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(
                {
                    "task_id": stt_task_id,
                    "status": "completed",
                    "segments": [{"id": 0, "start": 0.0, "end": 5.0, "text": "test"}],
                }
            )
            if "result" in key
            else None
        )
        mock_engine = _make_mock_engine()
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine.get_instance",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
            patch(
                "backend.services.sync_service.persist_task_result",
                side_effect=Exception("DB 연결 실패"),
            ),
        ):
            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # DB 저장 실패해도 완료 결과 반환됨 (line 351-352)
        assert result["status"] == "completed"

    def test_db_persist_failure_on_file_not_found_ignored(self, tmp_path: Path):
        """FileNotFoundError 경로에서 DB 저장 실패해도 결과 반환됨"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        # WAV 파일 없음

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(
                {
                    "task_id": stt_task_id,
                    "status": "completed",
                    "segments": [],
                }
            )
            if "result" in key
            else None
        )
        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch(
                "backend.services.sync_service.persist_task_result",
                side_effect=Exception("DB 오류"),
            ),
        ):
            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # FileNotFoundError 경로의 DB 저장 실패 무시됨 (line 407-408)
        assert result["status"] == "failed"

    def test_db_persist_failure_on_generic_error_ignored(self, tmp_path: Path):
        """일반 예외 경로에서 DB 저장 실패해도 결과 반환됨"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        (tmp_path / f"{stt_task_id}.wav").write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(
                {
                    "task_id": stt_task_id,
                    "status": "completed",
                    "segments": [],
                }
            )
            if "result" in key
            else None
        )
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.diarize.side_effect = RuntimeError("엔진 오류")

        mock_settings = _default_settings(tmp_path)

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine.get_instance",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings", mock_settings),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
            patch(
                "backend.services.sync_service.persist_task_result",
                side_effect=Exception("DB 오류"),
            ),
        ):
            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # 일반 예외 경로의 DB 저장 실패 무시됨 (line 435-436)
        assert result["status"] == "failed"
        assert "엔진 오류" in result["error_message"]
