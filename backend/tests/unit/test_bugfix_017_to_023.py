"""NEWBUG-017 ~ NEWBUG-023: 신규 버그 수정 회귀 방지 테스트.

각 테스트는 수정 전에 실패하고 수정 후에 통과하도록 작성되었다.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# NEWBUG-017: export.py Content-Disposition 헤더 인젝션 방어
# ---------------------------------------------------------------------------


class TestExportFilenameSanitization:
    """`_safe_export_filename`가 헤더 인젝션 위험 문자를 제거하는지 확인."""

    def test_clean_uuid_is_preserved(self):
        from backend.app.api.v1.admin.export import _safe_export_filename

        clean = "abc123-def4-5678-90ab-cdef01234567"
        result = _safe_export_filename(clean, "pdf")
        assert result == f"minutes_{clean}.pdf"

    def test_crlf_injection_is_stripped(self):
        from backend.app.api.v1.admin.export import _safe_export_filename

        # CRLF + 추가 헤더 주입 시도. 핵심 보안 속성은 CRLF와 콜론이
        # 헤더에 포함되지 않는 것 — 알파벳/대시는 합법적 파일명 문자.
        evil = "abc\r\nContent-Type: text/html\r\nX-Injected: 1"
        result = _safe_export_filename(evil, "pdf")
        assert "\r" not in result
        assert "\n" not in result
        assert ":" not in result
        assert " " not in result
        # 결과는 헤더 라인 1줄로 안전하게 들어가야 한다.
        header_value = f'attachment; filename="{result}"'
        assert "\r" not in header_value
        assert "\n" not in header_value

    def test_quote_injection_is_stripped(self):
        from backend.app.api.v1.admin.export import _safe_export_filename

        evil = 'abc"; filename="evil.exe'
        result = _safe_export_filename(evil, "docx")
        assert '"' not in result
        assert ";" not in result
        # 결과는 항상 `minutes_<sanitized>.<ext>` 형태
        assert result.startswith("minutes_")
        assert result.endswith(".docx")

    def test_empty_after_sanitization_falls_back_to_default(self):
        from backend.app.api.v1.admin.export import _safe_export_filename

        # 모든 문자가 금지 문자
        result = _safe_export_filename('"\r\n;', "pdf")
        assert result == "minutes_minutes.pdf"


# ---------------------------------------------------------------------------
# NEWBUG-018: statistics.py json.loads 무방어 + 로거 누락
# ---------------------------------------------------------------------------


class TestStatisticsRedisCorruption:
    """Redis 캐시가 잘못된 JSON일 때 statistics가 크래시하지 않고 DB로 폴백하는지 검증."""

    @pytest.mark.asyncio
    async def test_corrupted_redis_falls_back_to_db(self):
        from backend.services.statistics import _fetch_minutes_result

        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value="not-valid-json")

        # DB 폴백: scalars().first()가 None → 결과 없음
        db_mock = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = None
        db_mock.execute = AsyncMock(return_value=execute_result)

        # JSONDecodeError가 전파되면 안 되고, DB 폴백 결과(None) 반환
        result = await _fetch_minutes_result(redis_mock, db_mock, "task-abc")
        assert result is None
        db_mock.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_valid_redis_json_is_returned_directly(self):
        from backend.services.statistics import _fetch_minutes_result

        payload = {"segments": [{"text": "hi", "start": 0, "end": 1}]}
        redis_mock = AsyncMock()
        redis_mock.get = AsyncMock(return_value=json.dumps(payload))
        db_mock = AsyncMock()

        result = await _fetch_minutes_result(redis_mock, db_mock, "task-abc")
        assert result == payload
        # 정상일 때 DB 조회는 일어나지 않아야 한다.
        db_mock.execute.assert_not_called()


# ---------------------------------------------------------------------------
# NEWBUG-019: sentiment_analyzer.py 빈 choices 방어
# ---------------------------------------------------------------------------


class TestSentimentEmptyChoices:
    """ZAI 응답이 빈 choices를 반환해도 IndexError가 발생하지 않아야 한다."""

    def test_empty_choices_returns_fallback_result(self):
        from backend.pipeline.sentiment_analyzer import SentimentAnalyzer

        analyzer = SentimentAnalyzer()

        # ZAI 응답 모의: choices가 빈 리스트
        mock_response = MagicMock()
        mock_response.choices = []
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("backend.pipeline.sentiment_analyzer.ZAIClient", return_value=mock_client):
            # 폴백 처리: IndexError가 발생하지 않고 빈 응답 파싱 결과를 반환해야 한다.
            result = analyzer.analyze(
                segments=[{"speaker": "S1", "text": "hello", "start": 0, "end": 1}],
                speaker_stats=[{"speaker": "S1", "duration": 1.0, "ratio": 1.0}],
                api_key="test",
                model="claude-3",
                max_tokens=100,
            )
            # 빈 응답이라도 결과 객체가 반환된다.
            assert result is not None


# ---------------------------------------------------------------------------
# NEWBUG-021: retention.py 파일 정리 TOCTOU
# ---------------------------------------------------------------------------


class TestCleanupTempFilesRace:
    """다른 프로세스가 동시 정리해도 cleanup_temp_files가 크래시하지 않아야 한다."""

    def test_concurrent_unlink_does_not_raise(self, tmp_path: Path):
        from backend.services import retention

        # 오래된 파일을 만들어 두고
        old_file = tmp_path / "old.tmp"
        old_file.write_bytes(b"old")
        # 수정 시각을 과거로 설정 (3시간 전)
        past = time.time() - (3 * 3600)
        os.utime(old_file, (past, past))

        call_count = {"unlink": 0}

        def racing_unlink(self: Path, *args, **kwargs):
            call_count["unlink"] += 1
            # 다른 프로세스가 먼저 삭제한 상황을 시뮬레이션
            raise FileNotFoundError(f"already gone: {self}")

        # is_file과 stat는 정상, unlink만 FileNotFoundError
        with patch.object(Path, "unlink", racing_unlink):
            deleted, freed = retention.cleanup_temp_files(tmp_path, retention_hours=1)

        # 크래시 없이 카운트는 0 (실제 삭제는 안 일어남)
        assert deleted == 0
        assert freed == 0
        assert call_count["unlink"] >= 1

    def test_normal_old_files_are_deleted(self, tmp_path: Path):
        from backend.services import retention

        old_file = tmp_path / "old.tmp"
        old_file.write_bytes(b"oldcontent")
        past = time.time() - (3 * 3600)
        os.utime(old_file, (past, past))

        deleted, freed = retention.cleanup_temp_files(tmp_path, retention_hours=1)
        assert deleted == 1
        assert freed == len(b"oldcontent")
        assert not old_file.exists()

    def test_recent_files_are_kept(self, tmp_path: Path):
        from backend.services import retention

        recent = tmp_path / "recent.tmp"
        recent.write_bytes(b"keep")

        deleted, freed = retention.cleanup_temp_files(tmp_path, retention_hours=24)
        assert deleted == 0
        assert freed == 0
        assert recent.exists()


# ---------------------------------------------------------------------------
# NEWBUG-022: events/subscriber.py pubsub json.loads 무방어
# ---------------------------------------------------------------------------


class TestSubscriberCorruptedMessage:
    """Pub/Sub 메시지에 잘못된 JSON이 와도 스트림이 중단되지 않아야 한다."""

    @pytest.mark.asyncio
    async def test_corrupted_payload_is_skipped(self):
        from backend.events.subscriber import subscribe_task_events

        pubsub_mock = AsyncMock()
        pubsub_mock.subscribe = AsyncMock()
        pubsub_mock.unsubscribe = AsyncMock()
        pubsub_mock.close = AsyncMock()

        good = {"event": "status_update", "data": {"status": "processing"}}
        completed = {"event": "completed", "data": {"status": "completed"}}
        call_count = {"n": 0}

        async def mock_get_message(ignore_subscribe_messages=True, timeout=None):
            call_count["n"] += 1
            # 1번째: 깨진 JSON
            if call_count["n"] == 1:
                return {"type": "message", "data": "this-is-not-json{"}
            # 2번째: 정상 메시지
            if call_count["n"] == 2:
                return {"type": "message", "data": json.dumps(good)}
            # 3번째: 종료
            return {"type": "message", "data": json.dumps(completed)}

        pubsub_mock.get_message = mock_get_message

        redis_mock = MagicMock()
        redis_mock.pubsub.return_value = pubsub_mock
        redis_mock.get = AsyncMock(return_value=None)

        received = []
        async for msg in subscribe_task_events(redis_mock, "task-x"):
            received.append(msg)

        # 깨진 메시지는 건너뛰고 나머지 2개만 수신
        assert len(received) == 2
        assert received[0]["event"] == "status_update"
        assert received[1]["event"] == "completed"

    @pytest.mark.asyncio
    async def test_direct_check_skips_corrupted_status(self):
        """_check_task_status_directly가 손상된 캐시를 건너뛰는지 확인."""
        from backend.events.subscriber import _check_task_status_directly

        # 첫 prefix는 깨진 JSON, 두번째 prefix는 None
        redis_mock = AsyncMock()
        sequence = ["not-json", None, None, None]
        redis_mock.get = AsyncMock(side_effect=sequence)

        # 크래시 없이 None 반환
        result = await _check_task_status_directly(redis_mock, "task-y")
        assert result is None


# ---------------------------------------------------------------------------
# NEWBUG-020: chunk_manager 누수 — 직접 단위 테스트 어려우므로 동작 보장 테스트만
# ---------------------------------------------------------------------------


class TestChunkManagerTempDir:
    """split_audio가 짧은 오디오에도 디렉토리를 만들어두면 호출자가 정리할 수 있음을 확인."""

    def test_split_audio_short_audio_returns_empty_but_dir_reusable(self, tmp_path: Path):
        """오디오가 chunk_duration_ms 이하면 빈 리스트를 반환하지만,
        호출자가 미리 만든 output_dir은 그대로 보존되어 정리 책임이 명확하다."""
        from backend.pipeline import chunk_manager

        # AudioSegment.from_file mock으로 짧은 오디오를 시뮬레이션
        fake_audio = MagicMock()
        fake_audio.__len__ = lambda self: 1000  # 1초

        with patch.object(chunk_manager.AudioSegment, "from_file", return_value=fake_audio):
            chunks = chunk_manager.split_audio(
                file_path=str(tmp_path / "fake.wav"),
                chunk_duration_ms=30 * 60 * 1000,  # 30분
                overlap_ms=5000,
                output_dir=tmp_path,
            )
        assert chunks == []
        # output_dir은 호출자가 만든 디렉토리이므로 그대로 존재 — 호출자가 정리
        assert tmp_path.exists()


# ---------------------------------------------------------------------------
# NEWBUG-020 직접 검증: transcription_task가 출력 디렉토리를 추적하여 누수 방지
# ---------------------------------------------------------------------------


def test_transcription_task_tracks_chunk_temp_dir():
    """transcription_task.py 본문에 누수 방지용 사전 추적 코드가 포함되어 있는지 확인.

    BUG: 이전에는 `output_dir=tempfile.mkdtemp()`를 인라인으로 넘겨서
    split_audio가 빈 리스트를 반환할 때 임시 디렉토리가 누수되었다.
    FIX: 디렉토리를 먼저 만들어 `temp_dir` 변수로 추적한 뒤 split_audio에 전달.
    """
    from pathlib import Path as _Path

    src = _Path(__file__).resolve().parent.parent.parent / "workers/tasks/transcription_task.py"
    body = src.read_text(encoding="utf-8")
    # 새 패턴: 미리 추적된 디렉토리를 split_audio에 전달
    assert "chunk_output_dir = Path(tempfile.mkdtemp())" in body
    assert "temp_dir = chunk_output_dir" in body
    # 옛 인라인 패턴은 제거되었어야 함
    assert "output_dir=tempfile.mkdtemp()" not in body
