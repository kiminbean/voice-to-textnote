"""
SPEC-TONE-001 tone_task 단위 테스트
REQ-TONE-004: DIA wav 없으면 skipped 반환
REQ-TONE-005: tone_task 완료/실패 후 DIA wav 삭제
REQ-TONE-006: tone_task 실패 시 다른 파이프라인 태스크 무영향
REQ-TONE-007: DIA 완료 후 tone_task 트리거
REQ-TONE-008: celery_app include 리스트 등록
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_redis(active_count: int = 0) -> MagicMock:
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


def _configure_settings(mock_settings: MagicMock, tone_model: str = "egemaps-v2") -> None:
    mock_settings.tone_model = tone_model
    mock_settings.tone_result_ttl = 86400
    mock_settings.max_concurrent_tone = 1
    mock_settings.tone_min_segment_duration_sec = 0.5


def _make_tone_segments() -> list[dict]:
    return [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
    ]


def _make_engine_results() -> list[dict]:
    return [
        {
            "start": 0.0,
            "end": 2.0,
            "speaker": "SPEAKER_00",
            "tone": "calm",
            "confidence": 0.72,
            "prosody_features": {"f0_mean": 180.0, "f0_std": 12.0, "rms_energy": 0.05, "speaking_rate": 50.0},
        },
        {
            "start": 2.0,
            "end": 4.0,
            "speaker": "SPEAKER_01",
            "tone": "excited",
            "confidence": 0.68,
            "prosody_features": {"f0_mean": 220.0, "f0_std": 35.0, "rms_energy": 0.10, "speaking_rate": 80.0},
        },
    ]


# ---------------------------------------------------------------------------
# REQ-TONE-008: Celery 등록 테스트
# ---------------------------------------------------------------------------


class TestToneTaskRegistration:
    """tone_task Celery 등록 검증 (REQ-TONE-008, AC-TONE-001)"""

    def test_tone_task_registered_in_celery(self):
        """celery_app.conf.include 에 tone_task 가 등록되어 있어야 함"""
        from backend.workers.celery_app import celery_app

        assert "backend.workers.tasks.tone_task" in celery_app.conf.include

    def test_tone_task_callable(self):
        """tone_celery_task 가 유효한 Celery task 객체여야 함"""
        from backend.workers.tasks.tone_task import tone_celery_task

        assert hasattr(tone_celery_task, "delay")
        assert hasattr(tone_celery_task, "apply_async")
        assert hasattr(tone_celery_task, "run")


# ---------------------------------------------------------------------------
# REQ-TONE-007: DIA 완료 후 트리거 테스트
# ---------------------------------------------------------------------------


class TestToneTaskTrigger:
    """DIA 완료 후 tone_task 트리거 로직 (REQ-TONE-007, AC-TONE-002/006)"""

    def test_tone_task_skipped_when_model_empty(self, tmp_path: Path):
        """tone_model == "" 면 DIA 완료 후 tone_celery_task.delay() 호출 안 함 (AC-TONE-006)"""
        from backend.workers.tasks import diarization_task as dia_mod

        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.workers.tasks.diarization_task.DiarizationEngine") as mock_engine_cls,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=60.0),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.tone_celery_task") as mock_tone_task,
        ):
            mock_engine_inst = MagicMock()
            mock_engine_inst.is_loaded = True
            mock_engine_inst.diarize.return_value = []
            mock_engine_cls.get_instance.return_value = mock_engine_inst
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.huggingface_token = "fake-token"
            mock_settings.diarization_result_ttl = 604800
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 30
            mock_settings.dia_target_sample_rate = 0
            mock_settings.tone_model = ""

            dia_mod.diarization_task(
                task_id="dia-task-id",
                audio_path=str(wav_path),
            )

        mock_tone_task.delay.assert_not_called()

    def test_tone_task_triggered_when_model_set(self, tmp_path: Path):
        """tone_model != "" 면 DIA 완료 후 tone_celery_task.delay() 호출 (AC-TONE-002)"""
        from backend.workers.tasks import diarization_task as dia_mod

        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.workers.tasks.diarization_task.DiarizationEngine") as mock_engine_cls,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=60.0),
            patch("backend.workers.tasks.diarization_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.tone_celery_task") as mock_tone_task,
        ):
            mock_engine_inst = MagicMock()
            mock_engine_inst.is_loaded = True
            mock_seg = MagicMock()
            mock_seg.speaker_id = "SPEAKER_00"
            mock_seg.start = 0.0
            mock_seg.end = 2.0
            mock_engine_inst.diarize.return_value = [mock_seg]
            mock_engine_cls.get_instance.return_value = mock_engine_inst
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.huggingface_token = "fake-token"
            mock_settings.diarization_result_ttl = 604800
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 30
            mock_settings.dia_target_sample_rate = 0
            mock_settings.tone_model = "egemaps-v2"

            dia_mod.diarization_task(
                task_id="dia-task-id",
                audio_path=str(wav_path),
            )

        mock_tone_task.delay.assert_called_once()
        call_kwargs = mock_tone_task.delay.call_args.kwargs
        assert "dia_wav_path" in call_kwargs
        assert "segments" in call_kwargs


# ---------------------------------------------------------------------------
# REQ-TONE-004: DIA wav 없을 때 skipped
# ---------------------------------------------------------------------------


class TestToneTaskWavMissing:
    """DIA wav 파일 없을 때 skipped 처리 (REQ-TONE-004)"""

    def test_tone_task_skips_when_dia_wav_missing(self, tmp_path: Path):
        """DIA wav 파일이 존재하지 않으면 skipped 상태로 종료"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        missing_wav = str(tmp_path / "nonexistent.wav")

        mock_redis = _make_mock_redis()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
        ):
            _configure_settings(mock_settings)

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=missing_wav,
                segments=_make_tone_segments(),
            )

        assert result["status"] == "skipped"
        assert result["task_id"] == task_id


# ---------------------------------------------------------------------------
# REQ-TONE-005: DIA wav 삭제 테스트
# ---------------------------------------------------------------------------


class TestToneTaskWavDeletion:
    """tone_task 완료 후 DIA wav 삭제 (REQ-TONE-005)"""

    def test_tone_task_deletes_dia_wav_on_completion(self, tmp_path: Path):
        """tone_task 성공 후 DIA wav 파일 삭제"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy audio")
        assert wav_path.exists()

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.return_value = _make_engine_results()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "completed"
        assert not wav_path.exists(), "DIA wav 파일이 삭제되어야 함"

    def test_tone_task_deletes_dia_wav_on_failure(self, tmp_path: Path):
        """tone_task 실패 후에도 DIA wav 파일 삭제 (orphan 방지, REQ-TONE-005)"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy audio")
        assert wav_path.exists()

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.side_effect = RuntimeError("opensmile crash")

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "failed"
        assert not wav_path.exists(), "실패 후에도 DIA wav 파일이 삭제되어야 함 (orphan 방지)"


# ---------------------------------------------------------------------------
# REQ-TONE-006: 실패 격리 테스트
# ---------------------------------------------------------------------------


class TestToneTaskFailureIsolation:
    """tone_task 실패 시 다른 파이프라인 태스크 무영향 (REQ-TONE-006, AC-TONE-004)"""

    def test_tone_task_failure_isolated(self, tmp_path: Path):
        """ToneEngine 예외 발생 시 tone_task만 failed, 다른 태스크에 영향 없음"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.side_effect = MemoryError("19.2GB 초과")

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "failed"
        assert "19.2GB" in result["error_message"]


# ---------------------------------------------------------------------------
# Redis status tracking + result caching
# ---------------------------------------------------------------------------


class TestToneTaskRedisTracking:
    """Redis 상태 추적 및 결과 저장 테스트"""

    def test_tone_task_redis_status_tracking(self, tmp_path: Path):
        """pending → processing → completed 상태 전환이 Redis에 기록됨"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.return_value = _make_engine_results()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        status_keys = [
            call.args[0]
            for call in mock_redis.setex.call_args_list
            if call.args[0] == f"task:tone:status:{task_id}"
        ]
        assert len(status_keys) >= 2, "최소 processing + completed 상태 기록 필요"

        status_values = [
            json.loads(call.args[2])
            for call in mock_redis.setex.call_args_list
            if call.args[0] == f"task:tone:status:{task_id}"
        ]
        statuses = [sv["status"] for sv in status_values]
        assert "processing" in statuses
        assert "completed" in statuses

    def test_tone_task_result_stored_in_redis(self, tmp_path: Path):
        """완료된 결과가 task:tone:result:{task_id}에 TTL과 함께 저장됨"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.return_value = _make_engine_results()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        result_writes = [
            call
            for call in mock_redis.setex.call_args_list
            if call.args[0] == f"task:tone:result:{task_id}"
        ]
        assert result_writes, "task:tone:result:{task_id} 키로 결과가 저장되어야 함"
        assert result_writes[0].args[1] == 86400, "TTL이 tone_result_ttl과 일치해야 함"

        cached = json.loads(result_writes[0].args[2])
        assert cached["status"] == "completed"
        assert "segments" in cached
        assert "speakers" in cached
        assert "overall_tone" in cached


# ---------------------------------------------------------------------------
# 헬퍼 함수 단위 테스트
# ---------------------------------------------------------------------------


class TestToneTaskHelpers:
    """_get_redis, _update_task_status, _compute_overall_tone, _build_speaker_summary 테스트"""

    def test_get_redis_returns_worker_redis(self):
        """_get_redis()가 get_worker_redis()를 호출하여 Redis 클라이언트 반환"""
        from backend.workers.tasks import tone_task as tone_mod

        mock_redis = MagicMock()
        with patch("backend.workers.tasks.tone_task.get_worker_redis", return_value=mock_redis):
            result = tone_mod._get_redis()
        assert result is mock_redis

    def test_update_task_status_preserves_created_at(self):
        """_update_task_status 호출 시 기존 created_at 보존 (line 46-47, 56)"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks import tone_task as tone_mod

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = json.dumps(
            {"created_at": "2026-01-01T00:00:00+00:00", "status": "pending"}
        )

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
        ):
            _configure_settings(mock_settings)
            tone_mod._update_task_status(
                "task-id", TaskStatus.processing, 0.5, "처리 중", "some error"
            )

        stored = json.loads(mock_redis.setex.call_args.args[2])
        assert stored["created_at"] == "2026-01-01T00:00:00+00:00"
        assert stored["message"] == "처리 중"
        assert stored["error_message"] == "some error"

    def test_compute_overall_tone_empty_returns_unknown(self):
        """빈 세그먼트 또는 모두 skipped인 경우 unknown 반환 (line 146)"""
        from backend.workers.tasks.tone_task import _compute_overall_tone

        assert _compute_overall_tone([]) == "unknown"
        assert _compute_overall_tone([{"tone": "skipped"}]) == "unknown"
        assert _compute_overall_tone([{"tone": None}]) == "unknown"

    def test_compute_overall_tone_picks_most_common(self):
        """가장 빈도 높은 톤 반환"""
        from backend.workers.tasks.tone_task import _compute_overall_tone

        segments = [
            {"tone": "calm"},
            {"tone": "excited"},
            {"tone": "calm"},
            {"tone": "skipped"},
        ]
        assert _compute_overall_tone(segments) == "calm"

    def test_build_speaker_summary_aggregates_correctly(self):
        """다중 화자 세그먼트에서 화자별 톤 분포/평균 집계"""
        from backend.workers.tasks.tone_task import _build_speaker_summary

        segments = [
            {
                "speaker": "SPEAKER_00",
                "tone": "calm",
                "prosody_features": {"f0_mean": 180.0, "rms_energy": 0.05},
            },
            {
                "speaker": "SPEAKER_00",
                "tone": "calm",
                "prosody_features": {"f0_mean": 200.0, "rms_energy": 0.07},
            },
            {
                "speaker": "SPEAKER_01",
                "tone": "excited",
                "prosody_features": {"f0_mean": 250.0, "rms_energy": 0.10},
            },
        ]

        result = _build_speaker_summary(segments)
        assert len(result) == 2

        sp0 = next(s for s in result if s["speaker"] == "SPEAKER_00")
        assert sp0["dominant_tone"] == "calm"
        assert sp0["tone_distribution"] == {"calm": 2}
        assert sp0["avg_pitch"] == 190.0
        assert sp0["avg_energy"] == 0.06

        sp1 = next(s for s in result if s["speaker"] == "SPEAKER_01")
        assert sp1["dominant_tone"] == "excited"


# ---------------------------------------------------------------------------
# 동시성 제한 테스트 (line 198-210)
# ---------------------------------------------------------------------------


class TestToneTaskConcurrencyLimit:
    """max_concurrent_tone 초과 시 rejected 반환 테스트"""

    def test_tone_task_rejected_when_concurrent_limit_exceeded(self, tmp_path: Path):
        """활성 작업 수가 max_concurrent_tone 이상이면 rejected 반환"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis(active_count=1)

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
        ):
            _configure_settings(mock_settings)

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "rejected"
        assert "한도" in result["error_message"]


# ---------------------------------------------------------------------------
# SoftTimeLimitExceeded 및 OSError 처리 테스트 (lines 255-267, 289-290)
# ---------------------------------------------------------------------------


class TestToneTaskErrorHandling:
    """시간 초과 및 wav 삭제 OSError 테스트"""

    def test_tone_task_handles_soft_time_limit(self, tmp_path: Path):
        """SoftTimeLimitExceeded 발생 시 failed 상태로 종료 (line 255-267)"""
        from celery.exceptions import SoftTimeLimitExceeded

        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.side_effect = SoftTimeLimitExceeded()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "failed"
        assert "시간 초과" in result["error_message"]
        assert not wav_path.exists()

    def test_tone_task_swallows_oserror_on_wav_deletion(self, tmp_path: Path):
        """wav 삭제 중 OSError 발생해도 예외 전파되지 않음 (line 289-290)"""
        from backend.workers.tasks.tone_task import tone_task

        task_id = str(uuid.uuid4())
        wav_path = tmp_path / "test_dia.wav"
        wav_path.write_bytes(b"dummy")

        mock_redis = _make_mock_redis()
        mock_engine_inst = MagicMock()
        mock_engine_inst.analyze_segments.return_value = _make_engine_results()

        with (
            patch("backend.workers.tasks.tone_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.tone_task.settings") as mock_settings,
            patch("backend.workers.tasks.tone_task.publish_task_event_sync"),
            patch("backend.workers.tasks.tone_task.ToneEngine") as mock_engine_cls,
            patch("pathlib.Path.unlink", side_effect=OSError("permission denied")),
        ):
            _configure_settings(mock_settings)
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            # OSError가 전파되지 않고 정상 완료되어야 함
            result = tone_task(
                task_id=task_id,
                dia_task_id="dia-id",
                dia_wav_path=str(wav_path),
                segments=_make_tone_segments(),
            )

        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Celery wrapper 테스트 (lines 309-323)
# ---------------------------------------------------------------------------


class TestToneCeleryWrapper:
    """tone_celery_task wrapper 분기 검증"""

    def test_wrapper_handles_soft_time_limit(self):
        """SoftTimeLimitExceeded 발생 시 failed 반환"""
        from celery.exceptions import SoftTimeLimitExceeded

        from backend.workers.tasks.tone_task import tone_celery_task

        with patch(
            "backend.workers.tasks.tone_task.tone_task",
            side_effect=SoftTimeLimitExceeded(),
        ):
            result = tone_celery_task.run("task-id", "dia-id", "/tmp/x.wav", [])

        assert result["status"] == "failed"
        assert result["error"] == "시간 초과"

    def test_wrapper_retries_on_exception(self):
        """일반 예외 발생 시 self.retry 호출"""
        from backend.workers.tasks.tone_task import tone_celery_task

        with (
            patch(
                "backend.workers.tasks.tone_task.tone_task",
                side_effect=RuntimeError("temporary"),
            ),
            patch.object(
                tone_celery_task,
                "retry",
                side_effect=tone_celery_task.MaxRetriesExceededError(),
            ) as retry,
        ):
            result = tone_celery_task.run("task-id", "dia-id", "/tmp/x.wav", [])

        retry.assert_called_once()
        assert result["status"] == "failed"
        assert result["error"] == "temporary"
