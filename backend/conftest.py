"""
pytest 공유 픽스처 및 설정
SPEC-STT-001 테스트 스위트 기반 픽스처
"""

import io
import math
import struct
import wave
from datetime import UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 테스트 오디오 파일 픽스처
# ---------------------------------------------------------------------------


def _make_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """테스트용 최소 WAV 파일 바이트 생성 (440Hz 사인파)"""
    num_samples = int(sample_rate * duration_seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
            for i in range(num_samples)
        )
        wf.writeframes(frames)
    return buf.getvalue()


@pytest.fixture
def test_audio_bytes() -> bytes:
    """1초 테스트용 WAV 바이트"""
    return _make_wav_bytes(duration_seconds=1.0)


@pytest.fixture
def test_audio_file(tmp_path: Path) -> Path:
    """임시 디렉토리에 1초 WAV 파일 생성 후 Path 반환"""
    audio_path = tmp_path / "test_audio.wav"
    audio_path.write_bytes(_make_wav_bytes(duration_seconds=1.0))
    return audio_path


@pytest.fixture
def corrupted_audio_file(tmp_path: Path) -> Path:
    """손상된 오디오 파일 (디코딩 불가)"""
    corrupted_path = tmp_path / "corrupted.wav"
    corrupted_path.write_bytes(b"NOTAVALIDWAVFILE\x00\x01\x02\x03garbage data")
    return corrupted_path


@pytest.fixture
def invalid_format_file(tmp_path: Path) -> Path:
    """지원하지 않는 파일 형식 (.exe)"""
    exe_path = tmp_path / "malware.exe"
    exe_path.write_bytes(b"MZ\x90\x00" + b"\x00" * 100)
    return exe_path


# ---------------------------------------------------------------------------
# 표준 전사 결과 모의 데이터
# ---------------------------------------------------------------------------

MOCK_TRANSCRIPTION_RESULT = {
    "segments": [
        {
            "id": 0,
            "seek": 0,
            "start": 0.0,
            "end": 4.2,
            "text": "안녕하세요.",
            "tokens": [50364],
            "temperature": 0.0,
            "avg_logprob": -0.25,
            "compression_ratio": 1.1,
            "no_speech_prob": 0.05,
        }
    ],
    "language": "ko",
    "text": "안녕하세요.",
}


# ---------------------------------------------------------------------------
# WhisperEngine mock 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_whisper_engine():
    """
    WhisperEngine 싱글톤 mock - 실제 mlx_whisper 로드 없이 전사 결과 반환
    mlx_whisper는 함수 내부에서 import되므로 sys.modules 패치 사용
    """
    import sys

    mock_mlx = MagicMock()
    mock_mlx.transcribe.return_value = MOCK_TRANSCRIPTION_RESULT

    # mlx_whisper가 함수 내부에서 import되므로 sys.modules에 mock 주입
    with patch.dict(sys.modules, {"mlx_whisper": mock_mlx}):
        # WhisperEngine._detect_device → "mps" 반환
        with patch("backend.ml.stt_engine.WhisperEngine._detect_device", return_value="mps"):
            # 싱글톤 리셋 후 로드
            from backend.ml.stt_engine import WhisperEngine

            WhisperEngine._instance = None
            WhisperEngine._model_loaded = False
            WhisperEngine._load_time_seconds = None
            WhisperEngine._device = "cpu"

            engine = WhisperEngine.get_instance()
            engine.load()

            yield engine

            # 테스트 후 싱글톤 리셋
            WhisperEngine._instance = None
            WhisperEngine._model_loaded = False


# ---------------------------------------------------------------------------
# Redis mock 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_client():
    """Redis 비동기 클라이언트 mock"""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.ping.return_value = True
    return redis_mock


# ---------------------------------------------------------------------------
# Celery 작업 mock 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_celery_delay():
    """transcription_task.delay() mock - 즉시 task_id 반환"""
    mock_result = MagicMock()
    mock_result.id = "test-celery-task-id"

    with patch("backend.workers.tasks.transcription_task.transcription_task.delay") as mock_delay:
        mock_delay.return_value = mock_result
        yield mock_delay


# ---------------------------------------------------------------------------
# FastAPI TestClient 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def client(mock_redis_client, tmp_path):
    """
    FastAPI TestClient (단위/통합 테스트용)
    - WhisperEngine.load()를 mock하여 모델 미로드
    - Redis를 mock하여 실제 Redis 서버 불필요
    - Celery를 mock하여 즉시 task_id 반환
    - API Key 인증 비활성화 (기존 테스트 호환성 유지)
    """
    from fastapi.testclient import TestClient

    from backend.app.config import Settings
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app
    from backend.app.middleware.auth import verify_api_key

    # 임시 디렉토리를 스토리지로 사용
    test_settings = MagicMock(spec=Settings)
    test_settings.max_file_size_bytes = 500 * 1024 * 1024
    test_settings.max_file_size_mb = 500
    test_settings.max_duration_seconds = 4 * 3600
    test_settings.max_duration_hours = 4
    test_settings.max_concurrent_jobs = 3
    test_settings.temp_dir = tmp_path / "temp"
    test_settings.results_dir = tmp_path / "results"
    test_settings.cache_ttl_seconds = 86400
    test_settings.whisper_model = "mlx-community/whisper-large-v3-turbo"
    test_settings.whisper_language = "ko"
    test_settings.chunk_duration_ms = 30 * 60 * 1000
    test_settings.chunk_overlap_ms = 5000
    test_settings.memory_warning_threshold_mb = 19660
    # REQ-SEC-004: 테스트 환경에서 API Key 인증 비활성화 (api_keys 빈 목록)
    test_settings.api_keys = []
    test_settings.temp_dir.mkdir(parents=True, exist_ok=True)
    test_settings.results_dir.mkdir(parents=True, exist_ok=True)

    # FastAPI 의존성 오버라이드
    async def override_redis():
        return mock_redis_client

    # REQ-SEC-004: 테스트에서 API Key 검증 건너뜀 (개발 모드 동작 재현)
    async def override_verify_api_key():
        return "test-bypass"

    app.dependency_overrides[get_redis_client] = override_redis
    app.dependency_overrides[verify_api_key] = override_verify_api_key

    # lifespan 중 모델 로드 방지
    with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
        mock_engine_inst = MagicMock()
        mock_engine_inst.is_loaded = True
        mock_engine_inst.load.return_value = None
        mock_engine_cls.get_instance.return_value = mock_engine_inst

        with patch("backend.app.api.v1.transcription.settings", test_settings):
            with patch(
                "backend.pipeline.audio_processor.get_audio_duration_seconds", return_value=60.0
            ):
                with patch(
                    "backend.workers.tasks.transcription_task.transcription_task.delay"
                ) as mock_delay:
                    mock_task_result = MagicMock()
                    mock_task_result.id = "mock-task-id"
                    mock_delay.return_value = mock_task_result

                    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()


@pytest.fixture
def completed_task_data():
    """완료된 전사 작업 데이터 (Redis/파일 응답 시뮬레이션용)"""
    import uuid
    from datetime import datetime

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    return {
        "task_id": task_id,
        "status": "completed",
        "language": "ko",
        "duration": 4.2,
        "model": "mlx-community/whisper-large-v3-turbo",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 4.2,
                "text": "안녕하세요.",
                "confidence": 0.78,
            }
        ],
        "metadata": {
            "file_name": "test.wav",
            "file_size_bytes": 100000,
            "sample_rate": 16000,
            "processing_time_seconds": 2.5,
        },
        "created_at": now,
        "completed_at": now,
    }
