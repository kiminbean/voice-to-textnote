"""
화자 분리 Celery 태스크 단위 테스트 (RED phase)
REQ-DIA-013~018: 비동기 화자 분리 처리 워커
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------

MOCK_STT_RESULT = {
    "task_id": str(uuid.uuid4()),
    "status": "completed",
    "segments": [
        {"id": 0, "start": 0.0, "end": 5.0, "text": "안녕하세요.", "confidence": 0.9},
        {"id": 1, "start": 6.0, "end": 10.0, "text": "반갑습니다.", "confidence": 0.85},
    ],
    "language": "ko",
    "duration": 10.0,
}

MOCK_DIA_SEGMENTS = [
    {"speaker_id": "SPEAKER_00", "start": 0.0, "end": 5.0},
    {"speaker_id": "SPEAKER_01", "start": 6.0, "end": 10.0},
]


def _make_mock_redis():
    """Redis 동기 클라이언트 mock"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.scard.return_value = 0  # 활성 작업 수 기본값
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    pipe_mock = MagicMock()
    pipe_mock.incr.return_value = None
    pipe_mock.sadd.return_value = None
    pipe_mock.decr.return_value = None
    pipe_mock.srem.return_value = None
    pipe_mock.execute.return_value = [1, 1]
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


# ---------------------------------------------------------------------------
# Happy Path 테스트
# ---------------------------------------------------------------------------


class TestDiarizationTaskHappyPath:
    """정상 처리 흐름 테스트"""

    def test_task_returns_completed_result(self, tmp_path: Path):
        """STT 결과 존재, WAV 존재 → 완료 결과 반환"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        # WAV 파일 생성
        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )

        mock_engine = _make_mock_engine()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0
            mock_settings.cache_ttl_seconds = 604800

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "completed"
        assert result["task_id"] == task_id
        assert result["stt_task_id"] == stt_task_id

    def test_task_result_has_segments(self, tmp_path: Path):
        """완료 결과에 segments 포함"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )

        mock_engine = _make_mock_engine()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0
            mock_settings.cache_ttl_seconds = 604800

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert "segments" in result
        assert len(result["segments"]) == 2

    def test_task_caches_result_in_redis(self, tmp_path: Path):
        """완료 후 결과가 Redis에 캐싱됨 (24h TTL)"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )
        mock_engine = _make_mock_engine()

        with patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis):
            with patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ):
                with patch("backend.workers.tasks.diarization_task.settings") as mock_settings:
                    mock_settings.temp_dir = tmp_path
                    mock_settings.diarization_result_ttl = 86400
                    mock_settings.max_concurrent_diarizations = 2
                    mock_settings.huggingface_token = "hf_testtoken"
                    mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

                    diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # Redis setex 호출 확인
        assert mock_redis.setex.called


# ---------------------------------------------------------------------------
# 오류 처리 테스트
# ---------------------------------------------------------------------------


class TestDiarizationTaskErrors:
    """오류 조건 처리 테스트"""

    def test_wav_file_not_found_fails_immediately(self, tmp_path: Path):
        """WAV 파일 없음 → failed 상태로 즉시 실패"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        # WAV 파일 생성 안 함

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )

        with patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.diarization_task.settings") as mock_settings:
                mock_settings.temp_dir = tmp_path
                mock_settings.diarization_result_ttl = 86400
                mock_settings.max_concurrent_diarizations = 2
                mock_settings.huggingface_token = "hf_testtoken"
                mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

                result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "failed"

    def test_stt_result_not_found_fails_immediately(self, tmp_path: Path):
        """STT 결과 없음 → failed 상태로 즉시 실패"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None  # STT 결과 없음

        with patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.diarization_task.settings") as mock_settings:
                mock_settings.temp_dir = tmp_path
                mock_settings.diarization_result_ttl = 86400
                mock_settings.max_concurrent_diarizations = 2
                mock_settings.huggingface_token = "hf_testtoken"
                mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

                result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "failed"
        assert "error" in result or "error_message" in result

    def test_max_concurrent_limit_returns_failed(self, tmp_path: Path):
        """동시 실행 2개 한도 초과 시 failed 반환"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT)
            if "result" in key
            else "2"
            if key == "active_dia_jobs"
            else None
        )
        mock_redis.scard.return_value = 2  # 이미 2개 실행 중

        with patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.diarization_task.settings") as mock_settings:
                mock_settings.temp_dir = tmp_path
                mock_settings.diarization_result_ttl = 86400
                mock_settings.max_concurrent_diarizations = 2
                mock_settings.huggingface_token = "hf_testtoken"
                mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

                result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # 한도 초과 → failed (또는 429)
        assert result["status"] in ("failed", "rejected")

    def test_engine_error_updates_status_to_failed(self, tmp_path: Path):
        """DiarizationEngine 오류 → failed 상태 저장"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )

        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.diarize.side_effect = RuntimeError("Pipeline 오류")

        with patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis):
            with patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ):
                with patch("backend.workers.tasks.diarization_task.settings") as mock_settings:
                    mock_settings.temp_dir = tmp_path
                    mock_settings.diarization_result_ttl = 86400
                    mock_settings.max_concurrent_diarizations = 2
                    mock_settings.huggingface_token = "hf_testtoken"
                    mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

                    result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "failed"

    def test_failed_stt_result_propagates_upstream_error(self, tmp_path: Path):
        """선행 STT 실패 결과를 화자 분리 실패 원인으로 보존"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        (tmp_path / f"{stt_task_id}.wav").write_bytes(b"\x00" * 100)

        failed_stt = {
            "task_id": stt_task_id,
            "status": "failed",
            "error_message": "오디오 디코딩 실패",
        }
        mock_redis = _make_mock_redis()
        mock_redis.pipeline.return_value.execute.return_value = [0, 0]
        mock_redis.get.side_effect = lambda key: json.dumps(failed_stt) if "result" in key else None

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "failed"
        assert "오디오 디코딩 실패" in result["error_message"]

    def test_soft_time_limit_returns_failed_without_retrying(self, tmp_path: Path):
        """Soft time limit 초과 시 failed 결과를 반환"""
        from celery.exceptions import SoftTimeLimitExceeded

        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        (tmp_path / f"{stt_task_id}.wav").write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.pipeline.return_value.execute.return_value = [0, 0]
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.diarize.side_effect = SoftTimeLimitExceeded()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "failed"
        assert "60분" in result["error_message"]

    def test_chunked_diarization_used_at_threshold(self, tmp_path: Path):
        """임계 길이 이상 오디오는 chunked diarization 경로 사용"""
        from backend.pipeline.speaker_matcher import SpeakerSegment
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())
        (tmp_path / f"{stt_task_id}.wav").write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.pipeline.return_value.execute.return_value = [0, 0]
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )
        mock_engine = MagicMock()
        mock_engine.is_loaded = False

        def diarize_chunked_side_effect(*args, **kwargs):
            kwargs["progress_callback"](1, 2)
            return [
                SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
                SpeakerSegment(speaker_id="SPEAKER_01", start=6.0, end=10.0),
            ]

        mock_engine.diarize_chunked.side_effect = diarize_chunked_side_effect

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch(
                "backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=900.0
            ),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 30

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "completed"
        mock_engine.load.assert_called_once_with(
            hf_token="hf_testtoken",
            model_name="pyannote/speaker-diarization-3.1",
        )
        mock_engine.diarize_chunked.assert_called_once()
        chunked_kwargs = mock_engine.diarize_chunked.call_args.kwargs
        assert chunked_kwargs["chunk_duration_sec"] == 600
        assert chunked_kwargs["overlap_sec"] == 30


# ---------------------------------------------------------------------------
# 상태 전환 테스트
# ---------------------------------------------------------------------------


class TestDiarizationTaskStatusTransitions:
    """상태 전환: pending → processing → completed/failed"""

    def test_status_updated_to_processing_during_run(self, tmp_path: Path):
        """처리 중 status=processing으로 업데이트됨"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        status_updates = []

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )

        def track_setex(key, ttl, data):
            if "status" in key:
                status_updates.append(json.loads(data))
            return True

        mock_redis.setex.side_effect = track_setex

        mock_engine = _make_mock_engine()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0
            mock_settings.cache_ttl_seconds = 604800

            diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        # processing 또는 completed 상태 업데이트가 있었는지 확인
        statuses = [u.get("status") for u in status_updates if "status" in u]
        assert any(s in ("processing", "completed") for s in statuses)

    def test_final_status_is_completed_on_success(self, tmp_path: Path):
        """성공 시 최종 상태 = completed"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )
        mock_engine = _make_mock_engine()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0
            mock_settings.cache_ttl_seconds = 604800

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        assert result["status"] == "completed"

    def test_result_has_required_fields(self, tmp_path: Path):
        """완료 결과에 task_id, stt_task_id, status, segments, speakers 포함"""
        from backend.workers.tasks.diarization_task import diarization_task

        task_id = str(uuid.uuid4())
        stt_task_id = str(uuid.uuid4())

        wav_path = tmp_path / f"{stt_task_id}.wav"
        wav_path.write_bytes(b"\x00" * 100)

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_STT_RESULT) if "result" in key else None
        )
        mock_engine = _make_mock_engine()

        with (
            patch("backend.workers.tasks.diarization_task._get_redis", return_value=mock_redis),
            patch(
                "backend.workers.tasks.diarization_task.DiarizationEngine",
                return_value=mock_engine,
            ),
            patch("backend.workers.tasks.diarization_task.settings") as mock_settings,
            patch("backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=10.0),
        ):
            mock_settings.temp_dir = tmp_path
            mock_settings.diarization_result_ttl = 86400
            mock_settings.max_concurrent_diarizations = 2
            mock_settings.huggingface_token = "hf_testtoken"
            mock_settings.diarization_model = "pyannote/speaker-diarization-3.1"
            mock_settings.dia_chunk_threshold_minutes = 15
            mock_settings.dia_chunk_duration_minutes = 10
            mock_settings.dia_chunk_overlap_seconds = 5
            mock_settings.dia_target_sample_rate = 0
            mock_settings.cache_ttl_seconds = 604800

            result = diarization_task(task_id=task_id, stt_task_id=stt_task_id)

        for field in ("task_id", "stt_task_id", "status", "segments"):
            assert field in result, f"결과에 '{field}' 필드 누락"


class TestDiarizationCeleryWrapper:
    """diarization_celery_task wrapper 분기 검증"""

    def test_wrapper_returns_failed_for_soft_time_limit(self):
        from celery.exceptions import SoftTimeLimitExceeded

        from backend.workers.tasks.diarization_task import diarization_celery_task

        with patch(
            "backend.workers.tasks.diarization_task.diarization_task",
            side_effect=SoftTimeLimitExceeded(),
        ):
            result = diarization_celery_task.run("task-id", "stt-id")

        assert result == {"task_id": "task-id", "status": "failed", "error": "시간 초과"}

    def test_wrapper_returns_failed_for_missing_file(self):
        from backend.workers.tasks.diarization_task import diarization_celery_task

        with patch(
            "backend.workers.tasks.diarization_task.diarization_task",
            side_effect=FileNotFoundError("missing wav"),
        ):
            result = diarization_celery_task.run("task-id", "stt-id")

        assert result == {
            "task_id": "task-id",
            "status": "failed",
            "error": "missing wav",
        }

    def test_wrapper_returns_failed_after_max_retries(self):
        from backend.workers.tasks.diarization_task import diarization_celery_task

        with (
            patch(
                "backend.workers.tasks.diarization_task.diarization_task",
                side_effect=RuntimeError("temporary outage"),
            ),
            patch.object(
                diarization_celery_task,
                "retry",
                side_effect=diarization_celery_task.MaxRetriesExceededError(),
            ) as retry,
        ):
            result = diarization_celery_task.run("task-id", "stt-id")

        retry.assert_called_once()
        assert result["status"] == "failed"
        assert result["error"] == "temporary outage"
