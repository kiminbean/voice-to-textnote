"""
회의록 스키마 단위 테스트 (RED phase)
REQ-MIN-001~005 관련 Pydantic v2 스키마 검증
"""

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# MinutesCreateRequest 테스트
# ---------------------------------------------------------------------------


class TestMinutesCreateRequest:
    """POST /api/v1/minutes 요청 스키마 검증"""

    def test_valid_request_with_defaults(self):
        """diarization_task_id만 필수, 나머지는 기본값"""
        from backend.schemas.minutes import MinutesCreateRequest

        req = MinutesCreateRequest(diarization_task_id="task-abc-123")
        assert req.diarization_task_id == "task-abc-123"
        assert req.output_format == "json"
        assert req.speaker_names is None

    def test_valid_request_with_markdown_format(self):
        """output_format=markdown 허용"""
        from backend.schemas.minutes import MinutesCreateRequest

        req = MinutesCreateRequest(
            diarization_task_id="task-abc-123",
            output_format="markdown",
        )
        assert req.output_format == "markdown"

    def test_valid_request_with_speaker_names(self):
        """speaker_names 매핑 정상 수락"""
        from backend.schemas.minutes import MinutesCreateRequest

        req = MinutesCreateRequest(
            diarization_task_id="task-abc-123",
            speaker_names={"SPEAKER_00": "김팀장", "SPEAKER_01": "이팀원"},
        )
        assert req.speaker_names == {"SPEAKER_00": "김팀장", "SPEAKER_01": "이팀원"}

    def test_missing_diarization_task_id_raises_error(self):
        """diarization_task_id 없으면 ValidationError"""
        from backend.schemas.minutes import MinutesCreateRequest

        with pytest.raises(ValidationError):
            MinutesCreateRequest()  # type: ignore[call-arg]

    def test_speaker_names_none_is_valid(self):
        """speaker_names=None 명시적 허용"""
        from backend.schemas.minutes import MinutesCreateRequest

        req = MinutesCreateRequest(diarization_task_id="x", speaker_names=None)
        assert req.speaker_names is None


# ---------------------------------------------------------------------------
# MinutesSegment 테스트
# ---------------------------------------------------------------------------


class TestMinutesSegment:
    """회의록 세그먼트 스키마 검증"""

    def test_valid_segment_with_speaker(self):
        """speaker_id 포함 세그먼트 생성"""
        from backend.schemas.minutes import MinutesSegment

        seg = MinutesSegment(
            speaker_id="SPEAKER_00",
            speaker_name="Speaker 1",
            text="안녕하세요.",
            start=0.0,
            end=5.0,
        )
        assert seg.speaker_id == "SPEAKER_00"
        assert seg.speaker_name == "Speaker 1"
        assert seg.text == "안녕하세요."
        assert seg.start == 0.0
        assert seg.end == 5.0

    def test_valid_segment_with_null_speaker(self):
        """speaker_id=None 허용 (REQ-MIN-005: Unknown Speaker)"""
        from backend.schemas.minutes import MinutesSegment

        seg = MinutesSegment(
            speaker_id=None,
            speaker_name="Unknown Speaker",
            text="알 수 없는 발화",
            start=1.0,
            end=3.0,
        )
        assert seg.speaker_id is None
        assert seg.speaker_name == "Unknown Speaker"

    def test_segment_missing_required_fields_raises_error(self):
        """필수 필드 누락 시 ValidationError"""
        from backend.schemas.minutes import MinutesSegment

        with pytest.raises(ValidationError):
            MinutesSegment(speaker_id="SPEAKER_00")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SpeakerStats 테스트
# ---------------------------------------------------------------------------


class TestSpeakerStats:
    """화자 통계 스키마 검증"""

    def test_valid_speaker_stats(self):
        """정상적인 화자 통계 생성"""
        from backend.schemas.minutes import SpeakerStats

        stats = SpeakerStats(
            speaker_id="SPEAKER_00",
            speaker_name="Speaker 1",
            total_speaking_time=30.5,
            segment_count=3,
            speaking_ratio=45.2,
        )
        assert stats.speaker_id == "SPEAKER_00"
        assert stats.speaker_name == "Speaker 1"
        assert stats.total_speaking_time == 30.5
        assert stats.segment_count == 3
        assert stats.speaking_ratio == 45.2

    def test_zero_values_are_valid(self):
        """0값 허용"""
        from backend.schemas.minutes import SpeakerStats

        stats = SpeakerStats(
            speaker_id="SPEAKER_00",
            speaker_name="Speaker 1",
            total_speaking_time=0.0,
            segment_count=0,
            speaking_ratio=0.0,
        )
        assert stats.segment_count == 0

    def test_missing_required_fields_raises_error(self):
        """필수 필드 누락 시 ValidationError"""
        from backend.schemas.minutes import SpeakerStats

        with pytest.raises(ValidationError):
            SpeakerStats(speaker_id="SPEAKER_00")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MinutesResponse 테스트
# ---------------------------------------------------------------------------


class TestMinutesResponse:
    """회의록 응답 스키마 검증"""

    def test_valid_response_minimal(self):
        """최소 필드로 응답 생성"""
        from backend.schemas.minutes import MinutesResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesResponse(
            task_id="task-min-001",
            status=TaskStatus.completed,
            diarization_task_id="task-dia-001",
            segments=[],
            speakers=[],
            total_duration=0.0,
            total_speakers=0,
        )
        assert resp.task_id == "task-min-001"
        assert resp.status == TaskStatus.completed
        assert resp.markdown is None

    def test_valid_response_with_segments_and_speakers(self):
        """세그먼트 및 화자 통계 포함 응답"""
        from backend.schemas.minutes import MinutesResponse, MinutesSegment, SpeakerStats
        from backend.schemas.transcription import TaskStatus

        seg = MinutesSegment(
            speaker_id="SPEAKER_00",
            speaker_name="Speaker 1",
            text="Hello",
            start=0.0,
            end=5.0,
        )
        speaker = SpeakerStats(
            speaker_id="SPEAKER_00",
            speaker_name="Speaker 1",
            total_speaking_time=5.0,
            segment_count=1,
            speaking_ratio=100.0,
        )
        resp = MinutesResponse(
            task_id="task-min-001",
            status=TaskStatus.completed,
            diarization_task_id="task-dia-001",
            segments=[seg],
            speakers=[speaker],
            total_duration=5.0,
            total_speakers=1,
        )
        assert len(resp.segments) == 1
        assert len(resp.speakers) == 1

    def test_response_with_markdown(self):
        """markdown 필드 포함 응답"""
        from backend.schemas.minutes import MinutesResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesResponse(
            task_id="task-min-001",
            status=TaskStatus.completed,
            diarization_task_id="task-dia-001",
            segments=[],
            speakers=[],
            total_duration=10.0,
            total_speakers=1,
            markdown="**[00:00:00] Speaker 1**: Hello",
        )
        assert resp.markdown == "**[00:00:00] Speaker 1**: Hello"

    def test_response_default_lists(self):
        """segments/speakers 기본값 빈 리스트"""
        from backend.schemas.minutes import MinutesResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesResponse(
            task_id="t",
            status=TaskStatus.pending,
            diarization_task_id="d",
            total_duration=0.0,
            total_speakers=0,
        )
        assert resp.segments == []
        assert resp.speakers == []


# ---------------------------------------------------------------------------
# MinutesStatusResponse 테스트
# ---------------------------------------------------------------------------


class TestMinutesStatusResponse:
    """회의록 상태 응답 스키마 검증"""

    def test_valid_status_response(self):
        """정상 상태 응답 생성"""
        from backend.schemas.minutes import MinutesStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesStatusResponse(
            task_id="task-min-001",
            status=TaskStatus.processing,
            progress=0.5,
        )
        assert resp.task_id == "task-min-001"
        assert resp.status == TaskStatus.processing
        assert resp.progress == 0.5
        assert resp.message is None

    def test_status_response_with_message(self):
        """message 필드 포함"""
        from backend.schemas.minutes import MinutesStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesStatusResponse(
            task_id="task-min-001",
            status=TaskStatus.completed,
            progress=1.0,
            message="회의록 생성 완료",
        )
        assert resp.message == "회의록 생성 완료"

    def test_default_progress_is_zero(self):
        """progress 기본값 0.0"""
        from backend.schemas.minutes import MinutesStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = MinutesStatusResponse(
            task_id="t",
            status=TaskStatus.pending,
        )
        assert resp.progress == 0.0
