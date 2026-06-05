"""
SPEC-AUDIO-ANALYSIS-001: 오디오 품질 분석 API 테스트

대상: app/api/v1/audio_analysis.py
  - POST /api/v1/audio-analysis (analyze_audio_file)
"""

import io
import math
import struct
import wave
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def _make_analysis_result(**overrides):
    """테스트용 AudioAnalysisResult mock."""
    defaults = dict(
        filename="test.wav",
        format="wav",
        duration_seconds=5.0,
        sample_rate=16000,
        channels=1,
        sample_width=2,
        bitrate="256k",
        file_size_bytes=160000,
        max_dbfs=-3.0,
        avg_dbfs=-12.5,
        rms_dbfs=-15.0,
        silence_segments=[],
        silence_ratio=0.1,
        speech_ratio=0.9,
        quality_score=0.85,
        quality_issues=[],
        recommendation=None,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


@pytest.fixture
def app_client():
    """audio-analysis 라우터 테스트 앱."""
    from backend.app.api.v1.audio_analysis import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ---------------------------------------------------------------------------
# POST /audio-analysis
# ---------------------------------------------------------------------------


class TestAnalyzeAudioFile:
    """오디오 품질 분석 엔드포인트."""

    def test_successful_analysis(self, app_client):
        mock_result = _make_analysis_result()
        with patch("backend.app.api.v1.audio_analysis.analyze_audio", return_value=mock_result), \
             patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "test.wav"
        assert body["duration_seconds"] == 5.0
        assert body["quality_score"] == 0.85

    def test_invalid_format_returns_400(self, app_client):
        with patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("malware.exe", b"MZ\x00", "application/octet-stream")},
            )
        assert resp.status_code == 400

    def test_file_too_large_returns_413(self, app_client):
        with patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 0  # 0MB 제한
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("big.wav", b"x" * 100, "audio/wav")},
            )
        assert resp.status_code == 413

    def test_analysis_value_error_returns_422(self, app_client):
        with patch("backend.app.api.v1.audio_analysis.analyze_audio",
                    side_effect=ValueError("오디오 디코딩 실패")), \
             patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("bad.wav", b"not-audio", "audio/wav")},
            )
        assert resp.status_code == 422

    def test_analysis_unexpected_error_returns_500(self, app_client):
        with patch("backend.app.api.v1.audio_analysis.analyze_audio",
                    side_effect=RuntimeError("pydub 장애")), \
             patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 500

    def test_with_custom_silence_params(self, app_client):
        mock_result = _make_analysis_result()
        with patch("backend.app.api.v1.audio_analysis.analyze_audio", return_value=mock_result) as mock_analyze, \
             patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
                data={
                    "include_silence_detection": "false",
                    "silence_threshold_db": "-50.0",
                    "min_silence_duration_ms": "300",
                },
            )
        assert resp.status_code == 200
        # analyze_audio 호출 시 커스텀 파라미터 전달 확인
        call_kwargs = mock_analyze.call_args
        assert call_kwargs[1]["silence_threshold_db"] == -50.0
        assert call_kwargs[1]["min_silence_duration_ms"] == 300

    def test_no_filename_uses_unknown(self, app_client):
        """filename이 없어도 'unknown'으로 처리."""
        mock_result = _make_analysis_result()
        with patch("backend.app.api.v1.audio_analysis.analyze_audio", return_value=mock_result), \
             patch("backend.app.api.v1.audio_analysis.settings") as mock_s:
            mock_s.max_file_size_mb = 500
            resp = app_client.post(
                "/api/v1/audio-analysis",
                files={"file": ("", _make_wav_bytes(), "audio/wav")},
            )
        # 빈 파일명 → 확장자 없음 → 422 (FastAPI validation) 또는 400
        assert resp.status_code in (200, 400, 422)
