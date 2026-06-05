"""
SPEC-AUDIO-PREP-001: 오디오 전처리 API 단위 테스트

대상: app/api/v1/audio_preprocess.py
  - POST /audio/preprocess (preprocess_endpoint)
  - 정상/오류 경로 (503 비활성화, 400 포맷 오류, 422 옵션 검증)
"""

import io
import math
import struct
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers


def _make_wav_bytes(duration: float = 0.5, sr: int = 16000) -> bytes:
    """테스트용 최소 WAV 바이트."""
    n = int(sr * duration)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(16000 * math.sin(2 * math.pi * 440 * i / sr)))
            for i in range(n)
        )
        wf.writeframes(frames)
    return buf.getvalue()


@pytest.fixture
def app_client():
    """audio_preprocess 라우터 테스트 앱."""
    from backend.app.api.v1.audio_preprocess import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    # Redis override (미사용이지만 의존성 해결용)
    async def override_redis():
        return MagicMock()

    app.dependency_overrides[get_redis_client] = override_redis

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /audio/preprocess
# ---------------------------------------------------------------------------


class TestPreprocessEndpoint:
    """오디오 전처리 엔드포인트."""

    def test_disabled_returns_503(self, app_client):
        """전처리 비활성화 시 503."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s:
            mock_s.audio_preprocess_enabled = False
            resp = app_client.post(
                "/api/v1/audio/preprocess",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 503

    def test_invalid_format_returns_400(self, app_client):
        """지원하지 않는 포맷 → 400."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s, \
             patch("backend.app.api.v1.audio_preprocess.validate_audio_format", return_value=(False, "지원하지 않는 포맷")):
            mock_s.audio_preprocess_enabled = True
            resp = app_client.post(
                "/api/v1/audio/preprocess",
                files={"file": ("malware.exe", b"MZ\x00", "application/octet-stream")},
            )
        assert resp.status_code == 400

    def test_invalid_options_returns_422(self, app_client):
        """옵션 검증 실패 → 422."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s, \
             patch("backend.app.api.v1.audio_preprocess.validate_audio_format", return_value=(True, "")):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_default_high_pass_hz = 0
            # PreprocessOptions.validate()가 ValueError 발생하도록 mock
            with patch("backend.app.api.v1.audio_preprocess.PreprocessOptions") as mock_opts_cls:
                mock_opts = MagicMock()
                mock_opts.validate.side_effect = ValueError("잘못된 옵션")
                mock_opts_cls.return_value = mock_opts

                with patch("backend.app.api.v1.audio_preprocess.PreprocessOptionsPayload") as mock_payload:
                    mock_payload.return_value = MagicMock()

                    resp = app_client.post(
                        "/api/v1/audio/preprocess",
                        files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
                        data={"target_dbfs": "99.0"},  # 범위 밖
                    )
        assert resp.status_code == 422

    def test_file_too_large_returns_413(self, app_client):
        """파일 크기 초과 → 413."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s, \
             patch("backend.app.api.v1.audio_preprocess.validate_audio_format", return_value=(True, "")):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 0  # 0MB 제한
            mock_s.audio_preprocess_default_high_pass_hz = 0

            with patch("backend.app.api.v1.audio_preprocess._resolve_options") as mock_resolve:
                mock_resolve.return_value = MagicMock()

                resp = app_client.post(
                    "/api/v1/audio/preprocess",
                    files={"file": ("big.wav", b"x" * 100, "audio/wav")},
                )
        assert resp.status_code == 413

    def test_preprocess_failure_returns_500(self, app_client):
        """preprocess_audio 예외 → 500."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s, \
             patch("backend.app.api.v1.audio_preprocess.validate_audio_format", return_value=(True, "")), \
             patch("backend.app.api.v1.audio_preprocess._resolve_options", return_value=MagicMock()), \
             patch("backend.app.api.v1.audio_preprocess.preprocess_audio", side_effect=RuntimeError("ffmpeg 실패")), \
             patch("backend.app.api.v1.audio_preprocess._preprocess_semaphore"):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            resp = app_client.post(
                "/api/v1/audio/preprocess",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 500

    def test_preprocess_value_error_returns_400(self, app_client):
        """preprocess_audio ValueError → 400."""
        with patch("backend.app.api.v1.audio_preprocess.settings") as mock_s, \
             patch("backend.app.api.v1.audio_preprocess.validate_audio_format", return_value=(True, "")), \
             patch("backend.app.api.v1.audio_preprocess._resolve_options", return_value=MagicMock()), \
             patch("backend.app.api.v1.audio_preprocess.preprocess_audio", side_effect=ValueError("잘못된 오디오")), \
             patch("backend.app.api.v1.audio_preprocess._preprocess_semaphore"):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            resp = app_client.post(
                "/api/v1/audio/preprocess",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 400
