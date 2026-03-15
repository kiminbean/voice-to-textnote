"""
화자 분리 스키마 단위 테스트 (RED phase)
REQ-DIA-001, REQ-DIA-002 관련 Pydantic v2 스키마 검증
"""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# DiarizedSegmentResult 테스트
# ---------------------------------------------------------------------------


class TestDiarizedSegmentResult:
    """DiarizedSegmentResult 스키마 테스트"""

    def test_valid_diarized_segment_with_speaker(self):
        """화자 정보 포함한 유효한 세그먼트 생성"""
        from backend.schemas.diarization import DiarizedSegmentResult

        seg = DiarizedSegmentResult(
            id=0,
            start=0.0,
            end=4.2,
            text="안녕하세요.",
            confidence=0.85,
            speaker_id="SPEAKER_00",
            speaker_confidence=0.92,
        )
        assert seg.id == 0
        assert seg.start == 0.0
        assert seg.end == 4.2
        assert seg.text == "안녕하세요."
        assert seg.confidence == 0.85
        assert seg.speaker_id == "SPEAKER_00"
        assert seg.speaker_confidence == 0.92

    def test_diarized_segment_without_speaker(self):
        """화자 미식별 세그먼트 (speaker_id=None, speaker_confidence=0.0)"""
        from backend.schemas.diarization import DiarizedSegmentResult

        seg = DiarizedSegmentResult(
            id=1,
            start=5.0,
            end=8.0,
            text="테스트입니다.",
            confidence=0.7,
            speaker_id=None,
            speaker_confidence=0.0,
        )
        assert seg.speaker_id is None
        assert seg.speaker_confidence == 0.0

    def test_diarized_segment_default_speaker_id_is_none(self):
        """speaker_id 미지정 시 기본값 None"""
        from backend.schemas.diarization import DiarizedSegmentResult

        seg = DiarizedSegmentResult(
            id=0,
            start=0.0,
            end=1.0,
            text="텍스트",
            confidence=0.5,
        )
        assert seg.speaker_id is None
        assert seg.speaker_confidence == 0.0

    def test_speaker_confidence_range_validation(self):
        """speaker_confidence는 0.0~1.0 범위"""
        from backend.schemas.diarization import DiarizedSegmentResult

        # 유효한 범위
        seg = DiarizedSegmentResult(
            id=0, start=0.0, end=1.0, text="텍스트", confidence=0.5, speaker_confidence=1.0
        )
        assert seg.speaker_confidence == 1.0

    def test_speaker_confidence_below_zero_raises(self):
        """speaker_confidence < 0.0 → ValidationError"""
        from backend.schemas.diarization import DiarizedSegmentResult

        with pytest.raises(ValidationError):
            DiarizedSegmentResult(
                id=0,
                start=0.0,
                end=1.0,
                text="텍스트",
                confidence=0.5,
                speaker_confidence=-0.1,
            )

    def test_speaker_confidence_above_one_raises(self):
        """speaker_confidence > 1.0 → ValidationError"""
        from backend.schemas.diarization import DiarizedSegmentResult

        with pytest.raises(ValidationError):
            DiarizedSegmentResult(
                id=0,
                start=0.0,
                end=1.0,
                text="텍스트",
                confidence=0.5,
                speaker_confidence=1.1,
            )

    def test_diarized_segment_is_immutable(self):
        """frozen=True: 필드 변경 불가"""
        from backend.schemas.diarization import DiarizedSegmentResult

        seg = DiarizedSegmentResult(id=0, start=0.0, end=1.0, text="텍스트", confidence=0.5)
        with pytest.raises((ValidationError, TypeError)):
            seg.speaker_id = "SPEAKER_00"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SpeakerInfo 테스트
# ---------------------------------------------------------------------------


class TestSpeakerInfo:
    """SpeakerInfo 스키마 테스트"""

    def test_valid_speaker_info(self):
        """유효한 화자 정보 생성"""
        from backend.schemas.diarization import SpeakerInfo

        info = SpeakerInfo(
            speaker_id="SPEAKER_00",
            total_speaking_time=12.5,
            segment_count=3,
        )
        assert info.speaker_id == "SPEAKER_00"
        assert info.total_speaking_time == 12.5
        assert info.segment_count == 3

    def test_speaker_info_segment_count_non_negative(self):
        """segment_count는 0 이상"""
        from backend.schemas.diarization import SpeakerInfo

        info = SpeakerInfo(speaker_id="SPEAKER_01", total_speaking_time=0.0, segment_count=0)
        assert info.segment_count == 0

    def test_speaker_info_negative_segment_count_raises(self):
        """segment_count < 0 → ValidationError"""
        from backend.schemas.diarization import SpeakerInfo

        with pytest.raises(ValidationError):
            SpeakerInfo(speaker_id="SPEAKER_00", total_speaking_time=5.0, segment_count=-1)


# ---------------------------------------------------------------------------
# DiarizationCreateRequest 테스트
# ---------------------------------------------------------------------------


class TestDiarizationCreateRequest:
    """DiarizationCreateRequest 스키마 테스트"""

    def test_valid_create_request(self):
        """유효한 diarization 생성 요청"""
        from backend.schemas.diarization import DiarizationCreateRequest

        task_id = uuid.uuid4()
        req = DiarizationCreateRequest(stt_task_id=task_id)
        assert req.stt_task_id == task_id
        assert req.num_speakers is None
        assert req.min_speakers == 1
        assert req.max_speakers == 10

    def test_create_request_with_num_speakers(self):
        """num_speakers 지정 가능"""
        from backend.schemas.diarization import DiarizationCreateRequest

        req = DiarizationCreateRequest(stt_task_id=uuid.uuid4(), num_speakers=2)
        assert req.num_speakers == 2

    def test_create_request_num_speakers_min_one(self):
        """num_speakers는 1 이상"""
        from backend.schemas.diarization import DiarizationCreateRequest

        with pytest.raises(ValidationError):
            DiarizationCreateRequest(stt_task_id=uuid.uuid4(), num_speakers=0)

    def test_create_request_max_speakers_default_ten(self):
        """max_speakers 기본값 10"""
        from backend.schemas.diarization import DiarizationCreateRequest

        req = DiarizationCreateRequest(stt_task_id=uuid.uuid4())
        assert req.max_speakers == 10

    def test_create_request_min_speakers_default_one(self):
        """min_speakers 기본값 1"""
        from backend.schemas.diarization import DiarizationCreateRequest

        req = DiarizationCreateRequest(stt_task_id=uuid.uuid4())
        assert req.min_speakers == 1


# ---------------------------------------------------------------------------
# DiarizationResponse 테스트
# ---------------------------------------------------------------------------


class TestDiarizationResponse:
    """DiarizationResponse 스키마 테스트"""

    def test_valid_diarization_response(self):
        """완료 상태 diarization 응답 생성"""
        from backend.schemas.diarization import (
            DiarizationResponse,
            DiarizedSegmentResult,
            SpeakerInfo,
        )
        from backend.schemas.transcription import TaskStatus

        task_id = uuid.uuid4()
        now = datetime.now(UTC)

        segments = [
            DiarizedSegmentResult(
                id=0,
                start=0.0,
                end=4.2,
                text="안녕하세요.",
                confidence=0.85,
                speaker_id="SPEAKER_00",
                speaker_confidence=0.92,
            )
        ]
        speakers = [SpeakerInfo(speaker_id="SPEAKER_00", total_speaking_time=4.2, segment_count=1)]

        resp = DiarizationResponse(
            task_id=task_id,
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.completed,
            segments=segments,
            speakers=speakers,
            num_speakers=1,
            created_at=now,
            completed_at=now,
        )
        assert resp.task_id == task_id
        assert resp.status == TaskStatus.completed
        assert len(resp.segments) == 1
        assert len(resp.speakers) == 1
        assert resp.num_speakers == 1

    def test_diarization_response_default_empty_lists(self):
        """기본값: segments, speakers 빈 리스트"""
        from backend.schemas.diarization import DiarizationResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        resp = DiarizationResponse(
            task_id=uuid.uuid4(),
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.pending,
            created_at=now,
        )
        assert resp.segments == []
        assert resp.speakers == []
        assert resp.num_speakers is None

    def test_diarization_response_with_error(self):
        """실패 상태 응답에 error_message 포함"""
        from backend.schemas.diarization import DiarizationResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        resp = DiarizationResponse(
            task_id=uuid.uuid4(),
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.failed,
            error_message="HuggingFace 토큰 인증 실패",
            created_at=now,
        )
        assert resp.status == TaskStatus.failed
        assert resp.error_message == "HuggingFace 토큰 인증 실패"


# ---------------------------------------------------------------------------
# DiarizationStatusResponse 테스트
# ---------------------------------------------------------------------------


class TestDiarizationStatusResponse:
    """DiarizationStatusResponse 스키마 테스트"""

    def test_valid_status_response(self):
        """유효한 상태 응답 생성"""
        from backend.schemas.diarization import DiarizationStatusResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        resp = DiarizationStatusResponse(
            task_id=uuid.uuid4(),
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.processing,
            progress=0.5,
            message="화자 분리 처리 중...",
            created_at=now,
            updated_at=now,
        )
        assert resp.status == TaskStatus.processing
        assert resp.progress == 0.5
        assert resp.message == "화자 분리 처리 중..."

    def test_status_response_progress_range(self):
        """progress는 0.0~1.0 범위"""
        from backend.schemas.diarization import DiarizationStatusResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        # 유효 범위
        resp = DiarizationStatusResponse(
            task_id=uuid.uuid4(),
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.pending,
            progress=0.0,
            created_at=now,
            updated_at=now,
        )
        assert resp.progress == 0.0

    def test_status_response_progress_above_one_raises(self):
        """progress > 1.0 → ValidationError"""
        from backend.schemas.diarization import DiarizationStatusResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            DiarizationStatusResponse(
                task_id=uuid.uuid4(),
                stt_task_id=uuid.uuid4(),
                status=TaskStatus.pending,
                progress=1.1,
                created_at=now,
                updated_at=now,
            )

    def test_status_response_default_progress_zero(self):
        """progress 기본값 0.0"""
        from backend.schemas.diarization import DiarizationStatusResponse
        from backend.schemas.transcription import TaskStatus

        now = datetime.now(UTC)
        resp = DiarizationStatusResponse(
            task_id=uuid.uuid4(),
            stt_task_id=uuid.uuid4(),
            status=TaskStatus.pending,
            created_at=now,
            updated_at=now,
        )
        assert resp.progress == 0.0
