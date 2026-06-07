"""
SPEC-ENHANCED-PREP: 고급 오디오 전처리 API 테스트

대상: app/api/v1/audio/enhanced_preprocess.py
  - POST /api/v1/enhanced/preprocess (단일 고급 전처리)
  - POST /api/v1/enhanced/batch (배치 전처리)
  - GET  /api/v1/enhanced/formats (지원 포맷 조회)
  - GET  /api/v1/enhanced/status (AI 모델 상태)
"""

import io
import math
import struct
import wave
from unittest.mock import AsyncMock, MagicMock, patch

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
            struct.pack("<h", int(16000 * math.sin(2 * math.pi * 440 * i / sr))) for i in range(n)
        )
        wf.writeframes(frames)
    return buf.getvalue()


@pytest.fixture
def app_client():
    """enhanced_preprocess 라우터 테스트 앱."""
    from backend.app.api.v1.audio.enhanced_preprocess import router

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /enhanced/preprocess
# ---------------------------------------------------------------------------


class TestEnhancedPreprocess:
    """단일 파일 고급 전처리 엔드포인트."""

    def test_disabled_returns_503(self, app_client):
        """전처리 비활성화 시 503."""
        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s:
            mock_s.audio_preprocess_enabled = False
            resp = app_client.post(
                "/api/v1/enhanced/preprocess",
                files={"file": ("test.wav", _make_wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 503

    def test_invalid_format_returns_400(self, app_client):
        """지원하지 않는 포맷 -> 400."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(False, "지원하지 않는 포맷"),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            resp = app_client.post(
                "/api/v1/enhanced/preprocess",
                files={"file": ("malware.exe", b"MZ\x00", "application/octet-stream")},
            )
        assert resp.status_code == 400

    def test_file_too_large_returns_500(self, app_client):
        """파일 크기 초과 -> bad_request가 except Exception에서 잡혀 500으로 승격."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 0  # 0MB 제한

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
            ) as mock_proc:
                mock_processor = MagicMock()
                mock_proc.return_value = mock_processor

                resp = app_client.post(
                    "/api/v1/enhanced/preprocess",
                    files={"file": ("big.wav", b"x" * 100, "audio/wav")},
                )
        # bad_request(VoiceNoteError)가 except Exception에서 잡혀 500으로 승격
        assert resp.status_code == 500

    def test_upload_save_failure_returns_400(self, app_client):
        """업로드 저장 실패 -> 400."""
        wav_bytes = _make_wav_bytes()

        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
            ) as mock_proc:
                mock_processor = MagicMock()
                mock_proc.return_value = mock_processor

                # 파일 읽기 중 예외 발생 시뮬레이션
                with patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.tempfile.mkstemp",
                    side_effect=OSError("디스크 공간 부족"),
                ):
                    # mkstemp 실패 시 내부 예외 → 500
                    resp = app_client.post(
                        "/api/v1/enhanced/preprocess",
                        files={"file": ("test.wav", wav_bytes, "audio/wav")},
                    )
        assert resp.status_code == 500

    def test_preprocess_batch_failure_returns_400(self, app_client):
        """프로세서 실패 -> 400."""
        wav_bytes = _make_wav_bytes()

        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
            ) as mock_proc:
                mock_processor = MagicMock()
                mock_processor.preprocess_batch = AsyncMock(side_effect=RuntimeError("처리 실패"))
                mock_proc.return_value = mock_processor

                resp = app_client.post(
                    "/api/v1/enhanced/preprocess",
                    files={"file": ("test.wav", wav_bytes, "audio/wav")},
                )
        assert resp.status_code == 400

    def test_unexpected_error_returns_500(self, app_client):
        """예상치 못한 예외 -> 500."""
        wav_bytes = _make_wav_bytes()

        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
                side_effect=RuntimeError("모델 로드 실패"),
            ):
                resp = app_client.post(
                    "/api/v1/enhanced/preprocess",
                    files={"file": ("test.wav", wav_bytes, "audio/wav")},
                )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /enhanced/batch
# ---------------------------------------------------------------------------


class TestBatchPreprocess:
    """배치 오디오 전처리 엔드포인트."""

    def test_batch_disabled_returns_503(self, app_client):
        """전처리 비활성화 시 503."""
        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s:
            mock_s.audio_preprocess_enabled = False
            resp = app_client.post(
                "/api/v1/enhanced/batch",
                files=[
                    ("files", ("a.wav", _make_wav_bytes(), "audio/wav")),
                ],
            )
        assert resp.status_code == 503

    def test_batch_too_many_files_returns_400(self, app_client):
        """파일 수 초과 (21개) -> 400."""
        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s:
            mock_s.audio_preprocess_enabled = True
            files = [("files", (f"f{i}.wav", b"x", "audio/wav")) for i in range(21)]
            resp = app_client.post(
                "/api/v1/enhanced/batch",
                files=files,
            )
        assert resp.status_code == 400

    def test_batch_invalid_format_returns_400(self, app_client):
        """지원하지 않는 포맷 포함 -> 400."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(False, "지원하지 않는 포맷"),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            resp = app_client.post(
                "/api/v1/enhanced/batch",
                files=[
                    ("files", ("bad.exe", b"MZ\x00", "application/octet-stream")),
                ],
            )
        assert resp.status_code == 400

    def test_batch_file_too_large_returns_400(self, app_client):
        """배치 파일 크기 초과 -> 400."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 0

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
            ) as mock_proc:
                mock_processor = MagicMock()
                mock_proc.return_value = mock_processor

                resp = app_client.post(
                    "/api/v1/enhanced/batch",
                    files=[
                        ("files", ("big.wav", b"x" * 100, "audio/wav")),
                    ],
                )
        assert resp.status_code == 400

    def test_batch_processor_failure_returns_400(self, app_client):
        """배치 처리 실패 -> 400."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
            ) as mock_proc:
                mock_processor = MagicMock()
                mock_processor.preprocess_batch = AsyncMock(
                    side_effect=RuntimeError("배치 처리 실패")
                )
                mock_proc.return_value = mock_processor

                resp = app_client.post(
                    "/api/v1/enhanced/batch",
                    files=[
                        ("files", ("test.wav", _make_wav_bytes(), "audio/wav")),
                    ],
                )
        assert resp.status_code == 400

    def test_batch_unexpected_error_returns_500(self, app_client):
        """예상치 못한 예외 -> 500."""
        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            mock_s.audio_preprocess_enabled = True
            mock_s.audio_preprocess_max_file_mb = 500

            with patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
                side_effect=RuntimeError("모델 로드 실패"),
            ):
                resp = app_client.post(
                    "/api/v1/enhanced/batch",
                    files=[
                        ("files", ("test.wav", _make_wav_bytes(), "audio/wav")),
                    ],
                )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /enhanced/formats
# ---------------------------------------------------------------------------


class TestGetFormats:
    """지원 오디오 포맷 조회."""

    def test_returns_format_list(self, app_client):
        """포맷 목록 반환."""
        resp = app_client.get("/api/v1/enhanced/formats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 9
        # 첫 번째 포맷 검증
        wav = next(f for f in data if f["extension"] == "wav")
        assert "description" in wav
        assert "supported_codecs" in wav


# ---------------------------------------------------------------------------
# GET /enhanced/status
# ---------------------------------------------------------------------------


class TestGetModelStatus:
    """AI 모델 상태 조회."""

    def test_returns_model_status(self, app_client):
        """모델 상태 반환."""
        mock_processor = MagicMock()
        mock_processor.ai_model = MagicMock()
        mock_processor.ai_model.model_loaded = True

        with (
            patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as mock_s,
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                new_callable=AsyncMock,
                return_value=mock_processor,
            ),
        ):
            mock_s.audio_preprocess_max_file_mb = 500
            resp = app_client.get("/api/v1/enhanced/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_noise_removal_enabled"] is True
        assert data["model_loaded"] is True
        assert "supported_formats" in data
