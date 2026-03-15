"""
SpeakerMatcher 단위 테스트 (RED phase) - 100% 커버리지 목표
REQ-DIA-003~006: 타임스탬프 겹침 기반 화자 매칭
"""

import pytest

# ---------------------------------------------------------------------------
# 테스트 헬퍼 - SpeakerSegment, STT 세그먼트 생성
# ---------------------------------------------------------------------------


def _make_stt_segment(
    id: int, start: float, end: float, text: str = "텍스트", confidence: float = 0.8
) -> dict:
    """STT 세그먼트 딕셔너리 생성 헬퍼"""
    return {"id": id, "start": start, "end": end, "text": text, "confidence": confidence}


def _make_speaker_segment(speaker_id: str, start: float, end: float):
    """SpeakerSegment 나임드튜플 생성 헬퍼"""
    from backend.pipeline.speaker_matcher import SpeakerSegment

    return SpeakerSegment(speaker_id=speaker_id, start=start, end=end)


# ---------------------------------------------------------------------------
# 정상 매칭 테스트 (2명의 화자)
# ---------------------------------------------------------------------------


class TestNormalMatching:
    """정상적인 2명 화자 매칭"""

    def test_two_speakers_correctly_assigned(self):
        """2명의 화자 세그먼트가 올바르게 STT 세그먼트에 매핑됨"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [
            _make_stt_segment(0, 0.0, 5.0, "첫 번째 발화"),
            _make_stt_segment(1, 6.0, 10.0, "두 번째 발화"),
        ]
        dia_segments = [
            _make_speaker_segment("SPEAKER_00", 0.0, 5.0),
            _make_speaker_segment("SPEAKER_01", 6.0, 10.0),
        ]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert len(result) == 2
        assert result[0].speaker_id == "SPEAKER_00"
        assert result[1].speaker_id == "SPEAKER_01"

    def test_result_preserves_stt_fields(self):
        """결과에 원래 STT 필드(id, start, end, text, confidence) 보존됨"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [_make_stt_segment(0, 0.0, 3.0, "안녕하세요", 0.9)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 3.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].id == 0
        assert result[0].start == 0.0
        assert result[0].end == 3.0
        assert result[0].text == "안녕하세요"
        assert result[0].confidence == 0.9

    def test_speaker_confidence_calculation_full_overlap(self):
        """완전 겹침 → speaker_confidence = 1.0"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT 세그먼트: [0, 5), DIA 세그먼트: [0, 5) - 완전 겹침
        stt_segments = [_make_stt_segment(0, 0.0, 5.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 5.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].speaker_confidence == pytest.approx(1.0, abs=0.01)

    def test_speaker_confidence_calculation_partial_overlap(self):
        """부분 겹침 → speaker_confidence = overlap / segment_duration"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [0, 10), DIA: [0, 5) - 50% 겹침
        stt_segments = [_make_stt_segment(0, 0.0, 10.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 5.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        # overlap_time = 5.0, segment_duration = 10.0 → 0.5
        assert result[0].speaker_confidence == pytest.approx(0.5, abs=0.01)

    def test_result_returns_diarized_segment_result_type(self):
        """반환 타입이 DiarizedSegmentResult 리스트"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher
        from backend.schemas.diarization import DiarizedSegmentResult

        stt_segments = [_make_stt_segment(0, 0.0, 3.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 3.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert isinstance(result[0], DiarizedSegmentResult)

    def test_multiple_dia_segments_best_overlap_wins(self):
        """여러 DIA 세그먼트 중 겹침이 가장 큰 화자 선택"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [0, 10)
        # DIA: SPEAKER_00 [0, 3) overlap=3, SPEAKER_01 [2, 9) overlap=7
        stt_segments = [_make_stt_segment(0, 0.0, 10.0)]
        dia_segments = [
            _make_speaker_segment("SPEAKER_00", 0.0, 3.0),
            _make_speaker_segment("SPEAKER_01", 2.0, 9.0),
        ]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].speaker_id == "SPEAKER_01"


# ---------------------------------------------------------------------------
# 동점 처리 (Tie-breaking) 테스트
# ---------------------------------------------------------------------------


class TestTieBreaking:
    """동일 겹침 → 가장 빠른 시작 시간의 화자 선택 + 경고 로그"""

    def test_tie_breaking_picks_earliest_start(self):
        """동일 겹침 시 start_time이 더 작은 화자 선택"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [2, 6), 각 DIA 세그먼트와 겹침이 4초로 동일
        # SPEAKER_00: [0, 6) → overlap=[2,6) = 4초, start=0.0
        # SPEAKER_01: [2, 8) → overlap=[2,6) = 4초, start=2.0
        stt_segments = [_make_stt_segment(0, 2.0, 6.0)]
        dia_segments = [
            _make_speaker_segment("SPEAKER_00", 0.0, 6.0),
            _make_speaker_segment("SPEAKER_01", 2.0, 8.0),
        ]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        # 두 세그먼트 모두 겹침 = 4.0초
        # SPEAKER_00의 start(0.0) < SPEAKER_01의 start(2.0) → SPEAKER_00 선택
        assert result[0].speaker_id == "SPEAKER_00"

    def test_tie_breaking_logs_warning(self):
        """동점 시 경고 로그 발생 (structlog.warning 호출 확인)"""
        from unittest.mock import patch

        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [_make_stt_segment(0, 2.0, 6.0)]
        dia_segments = [
            _make_speaker_segment("SPEAKER_00", 0.0, 6.0),
            _make_speaker_segment("SPEAKER_01", 2.0, 8.0),
        ]

        matcher = SpeakerMatcher()
        with patch("backend.pipeline.speaker_matcher.logger") as mock_logger:
            matcher.match(stt_segments, dia_segments)
            # structlog warning 호출 확인
            mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# 겹침 없음 (No Overlap) 테스트
# ---------------------------------------------------------------------------


class TestNoOverlap:
    """겹침이 없는 경우 speaker_id=None, speaker_confidence=0.0"""

    def test_no_overlap_returns_none_speaker(self):
        """겹치는 DIA 세그먼트 없음 → speaker_id=None"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [0, 3), DIA: [5, 10) - 겹침 없음
        stt_segments = [_make_stt_segment(0, 0.0, 3.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 5.0, 10.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].speaker_id is None
        assert result[0].speaker_confidence == 0.0

    def test_no_overlap_confidence_is_zero(self):
        """겹침 없음 시 speaker_confidence == 0.0"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [_make_stt_segment(0, 10.0, 15.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 5.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].speaker_confidence == 0.0


# ---------------------------------------------------------------------------
# 빈 DIA 결과 테스트
# ---------------------------------------------------------------------------


class TestEmptyDiaResult:
    """DIA 결과가 비어있는 경우"""

    def test_empty_dia_all_segments_get_none_speaker(self):
        """DIA 결과 빈 리스트 → 모든 세그먼트 speaker_id=None"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [
            _make_stt_segment(0, 0.0, 3.0),
            _make_stt_segment(1, 4.0, 7.0),
        ]
        dia_segments = []  # 빈 결과

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert len(result) == 2
        assert all(seg.speaker_id is None for seg in result)
        assert all(seg.speaker_confidence == 0.0 for seg in result)

    def test_empty_dia_preserves_segment_count(self):
        """DIA 빈 결과에서도 STT 세그먼트 수는 유지됨"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [_make_stt_segment(i, float(i * 3), float(i * 3 + 2)) for i in range(5)]
        dia_segments = []

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert len(result) == 5


# ---------------------------------------------------------------------------
# 빈 STT 결과 테스트
# ---------------------------------------------------------------------------


class TestEmptySTTResult:
    """STT 결과가 비어있는 경우"""

    def test_empty_stt_returns_empty_list(self):
        """STT 세그먼트 빈 리스트 → 빈 리스트 반환"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = []
        dia_segments = [_make_speaker_segment("SPEAKER_00", 0.0, 5.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result == []

    def test_both_empty_returns_empty_list(self):
        """STT와 DIA 모두 빈 리스트 → 빈 리스트 반환"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        matcher = SpeakerMatcher()
        result = matcher.match([], [])

        assert result == []


# ---------------------------------------------------------------------------
# 경계값 테스트
# ---------------------------------------------------------------------------


class TestBoundaryValues:
    """경계값: 정확히 동일한 start/end"""

    def test_exact_same_boundaries(self):
        """STT와 DIA 세그먼트 경계가 정확히 동일 (start/end 같음)"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        stt_segments = [_make_stt_segment(0, 1.0, 4.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 1.0, 4.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        assert result[0].speaker_id == "SPEAKER_00"
        assert result[0].speaker_confidence == pytest.approx(1.0, abs=0.01)

    def test_touching_boundaries_no_overlap(self):
        """STT end == DIA start → 겹침 없음"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [0, 3), DIA: [3, 6) - 경계만 맞닿음
        stt_segments = [_make_stt_segment(0, 0.0, 3.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 3.0, 6.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        # 정확히 맞닿는 경우 겹침=0 → speaker_id=None
        assert result[0].speaker_id is None

    def test_single_sample_overlap(self):
        """아주 작은 겹침도 화자 할당됨"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # STT: [0, 10), DIA: [9.9, 20) - 0.1초 겹침
        stt_segments = [_make_stt_segment(0, 0.0, 10.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 9.9, 20.0)]

        matcher = SpeakerMatcher()
        result = matcher.match(stt_segments, dia_segments)

        # 겹침 > 0 → 화자 할당
        assert result[0].speaker_id == "SPEAKER_00"
        # confidence = 0.1 / 10.0 = 0.01
        assert result[0].speaker_confidence == pytest.approx(0.01, abs=0.001)

    def test_zero_duration_stt_segment(self):
        """STT 세그먼트 길이가 0 → ZeroDivisionError 없이 처리"""
        from backend.pipeline.speaker_matcher import SpeakerMatcher

        # start == end → 길이 0
        stt_segments = [_make_stt_segment(0, 5.0, 5.0)]
        dia_segments = [_make_speaker_segment("SPEAKER_00", 4.0, 6.0)]

        matcher = SpeakerMatcher()
        # ZeroDivisionError 없이 처리되어야 함
        result = matcher.match(stt_segments, dia_segments)
        assert len(result) == 1
        # 길이 0이면 신뢰도 0
        assert result[0].speaker_confidence == 0.0


# ---------------------------------------------------------------------------
# SpeakerSegment 타입 테스트
# ---------------------------------------------------------------------------


class TestSpeakerSegment:
    """SpeakerSegment NamedTuple 테스트"""

    def test_speaker_segment_fields(self):
        """SpeakerSegment에 speaker_id, start, end 필드 존재"""
        from backend.pipeline.speaker_matcher import SpeakerSegment

        seg = SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0)
        assert seg.speaker_id == "SPEAKER_00"
        assert seg.start == 0.0
        assert seg.end == 5.0

    def test_speaker_segment_is_named_tuple(self):
        """SpeakerSegment는 NamedTuple"""
        from backend.pipeline.speaker_matcher import SpeakerSegment

        seg = SpeakerSegment(speaker_id="SPEAKER_00", start=1.0, end=3.0)
        assert isinstance(seg, tuple)
