"""
오디오 파일 스트리밍 API 단위 테스트
Phase 2 (REQ-AUDIO-001): 인앱 오디오 재생 엔드포인트
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.exceptions import BadRequestError

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_audio_dir(tmp_path):
    """테스트용 오디오 파일이 있는 임시 디렉토리"""
    return tmp_path


@pytest.fixture
def client_with_audio(temp_audio_dir):
    """audio API 테스트 클라이언트"""
    from backend.app.main import app

    with patch("backend.app.api.v1.audio.audio.settings") as mock_settings:
        mock_settings.temp_dir = temp_audio_dir

        with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
            mock_engine_inst = MagicMock()
            mock_engine_inst.is_loaded = True
            mock_engine_inst.load.return_value = None
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            yield TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# 오디오 파일 조회 테스트
# ---------------------------------------------------------------------------


class TestGetMeetingAudio:
    """GET /api/v1/meetings/{task_id}/audio 테스트"""

    def test_returns_audio_file_when_exists(self, client_with_audio, temp_audio_dir):
        """task_id에 해당하는 오디오 파일이 존재하면 파일 반환"""
        # wav 파일 생성
        audio_file = temp_audio_dir / "task-123.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        response = client_with_audio.get("/api/v1/meetings/task-123/audio")

        assert response.status_code == 200
        assert response.headers["content-type"] in (
            "audio/wav",
            "audio/x-wav",
            "application/octet-stream",
        )

    def test_requires_api_key_for_audio_file_in_production(self, temp_audio_dir):
        """프로덕션에서는 원본 회의 오디오 파일을 API key 없이 다운로드할 수 없다."""
        from backend.app.main import app

        audio_file = temp_audio_dir / "task-123.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

        with (
            patch("backend.app.api.v1.audio.audio.settings") as mock_audio_settings,
            patch("backend.app.middleware.auth.settings") as mock_auth_settings,
            patch("backend.app.main.WhisperEngine") as mock_engine_cls,
        ):
            mock_audio_settings.temp_dir = temp_audio_dir
            mock_auth_settings.api_keys = ["prod-key"]
            mock_auth_settings.environment = "production"
            mock_engine_inst = MagicMock()
            mock_engine_inst.is_loaded = True
            mock_engine_inst.load.return_value = None
            mock_engine_cls.get_instance.return_value = mock_engine_inst

            response = TestClient(app, raise_server_exceptions=True).get(
                "/api/v1/meetings/task-123/audio"
            )

        assert response.status_code == 401

    def test_returns_mp3_file(self, client_with_audio, temp_audio_dir):
        """mp3 확장자 파일 반환"""
        audio_file = temp_audio_dir / "task-mp3.mp3"
        audio_file.write_bytes(b"ID3" + b"\x00" * 50)

        response = client_with_audio.get("/api/v1/meetings/task-mp3/audio")

        assert response.status_code == 200

    def test_returns_404_when_no_audio_file(self, client_with_audio, temp_audio_dir):
        """task_id에 해당하는 오디오 파일이 없으면 404"""
        response = client_with_audio.get("/api/v1/meetings/nonexistent/audio")

        assert response.status_code == 404

    def test_returns_404_when_temp_dir_missing(self, tmp_path):
        """temp_dir이 존재하지 않으면 404"""
        from backend.app.main import app

        nonexistent = tmp_path / "no_such_dir"

        with patch("backend.app.api.v1.audio.audio.settings") as mock_settings:
            mock_settings.temp_dir = nonexistent

            with patch("backend.app.main.WhisperEngine") as mock_engine_cls:
                mock_engine_inst = MagicMock()
                mock_engine_inst.is_loaded = True
                mock_engine_inst.load.return_value = None
                mock_engine_cls.get_instance.return_value = mock_engine_inst

                client = TestClient(app, raise_server_exceptions=True)
                response = client.get("/api/v1/meetings/task-x/audio")

        assert response.status_code == 404

    def test_searches_multiple_extensions(self, client_with_audio, temp_audio_dir):
        """지원 포맷 순서대로 검색하여 첫 매칭 반환"""
        # m4a만 존재 (wav, mp3 없음)
        audio_file = temp_audio_dir / "task-m4a.m4a"
        audio_file.write_bytes(b"\x00" * 50)

        response = client_with_audio.get("/api/v1/meetings/task-m4a/audio")

        assert response.status_code == 200

    def test_prefers_earlier_extension_format(self, client_with_audio, temp_audio_dir):
        """동일 task_id로 여러 확장자가 있으면 우선순위 높은 것 반환"""
        # wav와 mp3 모두 존재
        wav_file = temp_audio_dir / "task-multi.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 10)
        mp3_file = temp_audio_dir / "task-multi.mp3"
        mp3_file.write_bytes(b"ID3" + b"\x00" * 10)

        response = client_with_audio.get("/api/v1/meetings/task-multi/audio")

        assert response.status_code == 200
        # wav가 mp3보다 우선
        assert "task-multi.wav" in response.headers.get(
            "content-disposition", ""
        ) or response.headers["content-type"] in ("audio/wav", "audio/x-wav")

    @pytest.mark.asyncio
    async def test_rejects_task_id_path_traversal_before_file_lookup(self, temp_audio_dir):
        """함수 직접 호출에서도 temp_dir 밖 파일을 task_id로 참조하지 않는다."""
        from backend.app.api.v1.audio.audio import get_meeting_audio

        outside_audio = temp_audio_dir.parent / "outside.wav"
        outside_audio.write_bytes(b"RIFF" + b"\x00" * 10)

        with patch("backend.app.api.v1.audio.audio.settings") as mock_settings:
            mock_settings.temp_dir = temp_audio_dir

            with pytest.raises(BadRequestError) as exc_info:
                await get_meeting_audio("../outside")

        assert exc_info.value.status_code == 400
        assert outside_audio.exists()
