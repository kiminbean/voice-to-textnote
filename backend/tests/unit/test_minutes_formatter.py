"""
MinutesFormatter 단위 테스트 (RED phase)
REQ-MIN-001~005: 화자 그룹 병합, 통계 계산, 형식 변환
100% 커버리지 목표
"""

import pytest

from backend.schemas.diarization import DiarizedSegmentResult

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


def _make_segment(
    seg_id: int,
    start: float,
    end: float,
    text: str,
    speaker_id: str | None = "SPEAKER_00",
    confidence: float = 0.9,
) -> DiarizedSegmentResult:
    """테스트용 DiarizedSegmentResult 생성 헬퍼"""
    return DiarizedSegmentResult(
        id=seg_id,
        start=start,
        end=end,
        text=text,
        confidence=confidence,
        speaker_id=speaker_id,
        speaker_confidence=0.95,
    )


# ---------------------------------------------------------------------------
# MinutesFormatter.format_minutes() 테스트
# ---------------------------------------------------------------------------


class TestFormatMinutes:
    """format_minutes(): DiarizedSegmentResult 목록 → MinutesSegment 목록 변환"""

    def test_empty_input_returns_empty_list(self):
        """빈 입력 → 빈 결과"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        result = formatter.format_minutes([])
        assert result == []

    def test_single_segment_no_merge(self):
        """세그먼트 하나 → 그대로 반환"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [_make_segment(0, 0.0, 5.0, "안녕하세요.", "SPEAKER_00")]
        result = formatter.format_minutes(segs)
        assert len(result) == 1
        assert result[0].text == "안녕하세요."
        assert result[0].speaker_name == "Speaker 1"

    def test_consecutive_same_speaker_merged(self):
        """연속된 같은 화자 세그먼트 → 하나로 병합 (REQ-MIN-001)"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 3.0, "안녕하세요.", "SPEAKER_00"),
            _make_segment(1, 3.0, 6.0, "반갑습니다.", "SPEAKER_00"),
        ]
        result = formatter.format_minutes(segs)
        assert len(result) == 1
        assert "안녕하세요." in result[0].text
        assert "반갑습니다." in result[0].text

    def test_different_speakers_not_merged(self):
        """다른 화자는 병합되지 않음"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 3.0, "안녕하세요.", "SPEAKER_00"),
            _make_segment(1, 3.0, 6.0, "반갑습니다.", "SPEAKER_01"),
        ]
        result = formatter.format_minutes(segs)
        assert len(result) == 2

    def test_non_consecutive_same_speaker_not_merged(self):
        """연속되지 않은 같은 화자 → 병합되지 않음"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 3.0, "첫 번째.", "SPEAKER_00"),
            _make_segment(1, 3.0, 6.0, "두 번째.", "SPEAKER_01"),
            _make_segment(2, 6.0, 9.0, "세 번째.", "SPEAKER_00"),
        ]
        result = formatter.format_minutes(segs)
        assert len(result) == 3

    def test_null_speaker_becomes_unknown_speaker(self):
        """speaker_id=None → 'Unknown Speaker' (REQ-MIN-005)"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [_make_segment(0, 0.0, 5.0, "알 수 없는 발화.", speaker_id=None)]
        result = formatter.format_minutes(segs)
        assert len(result) == 1
        assert result[0].speaker_name == "Unknown Speaker"
        assert result[0].speaker_id is None

    def test_null_speaker_segments_merged(self):
        """연속된 speaker_id=None 세그먼트도 병합"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 3.0, "첫 문장.", speaker_id=None),
            _make_segment(1, 3.0, 6.0, "두 번째 문장.", speaker_id=None),
        ]
        result = formatter.format_minutes(segs)
        assert len(result) == 1
        assert result[0].speaker_name == "Unknown Speaker"

    def test_custom_speaker_names_applied(self):
        """speaker_names 매핑 적용 (REQ-MIN-017)"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter(speaker_names={"SPEAKER_00": "김팀장"})
        segs = [_make_segment(0, 0.0, 5.0, "안녕하세요.", "SPEAKER_00")]
        result = formatter.format_minutes(segs)
        assert result[0].speaker_name == "김팀장"

    def test_auto_speaker_name_generation(self):
        """speaker_names 없으면 자동 생성 (REQ-MIN-016): SPEAKER_00 → 'Speaker 1'"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 3.0, "첫 번째.", "SPEAKER_00"),
            _make_segment(1, 3.0, 6.0, "두 번째.", "SPEAKER_01"),
        ]
        result = formatter.format_minutes(segs)
        names = {r.speaker_name for r in result}
        assert "Speaker 1" in names
        assert "Speaker 2" in names

    def test_merged_segment_start_time_is_first(self):
        """병합된 세그먼트 시작 시간 = 첫 번째 세그먼트 시작"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 1.5, 4.0, "첫 문장.", "SPEAKER_00"),
            _make_segment(1, 4.0, 7.5, "두 번째 문장.", "SPEAKER_00"),
        ]
        result = formatter.format_minutes(segs)
        assert result[0].start == 1.5

    def test_merged_segment_end_time_is_last(self):
        """병합된 세그먼트 종료 시간 = 마지막 세그먼트 종료"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        segs = [
            _make_segment(0, 0.0, 4.0, "첫 문장.", "SPEAKER_00"),
            _make_segment(1, 4.0, 8.5, "두 번째 문장.", "SPEAKER_00"),
        ]
        result = formatter.format_minutes(segs)
        assert result[0].end == 8.5


# ---------------------------------------------------------------------------
# MinutesFormatter.calculate_speaker_stats() 테스트
# ---------------------------------------------------------------------------


class TestCalculateSpeakerStats:
    """calculate_speaker_stats(): 화자별 통계 계산 (REQ-MIN-002)"""

    def test_empty_input_returns_empty_list(self):
        """빈 입력 → 빈 통계"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        result = formatter.calculate_speaker_stats([], total_duration=0.0)
        assert result == []

    def test_single_speaker_stats(self):
        """단일 화자 통계 계산"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="Hello",
                start=0.0,
                end=10.0,
            )
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=10.0)
        assert len(stats) == 1
        assert stats[0].speaker_id == "SPEAKER_00"
        assert stats[0].total_speaking_time == pytest.approx(10.0)
        assert stats[0].segment_count == 1
        assert stats[0].speaking_ratio == pytest.approx(100.0)

    def test_two_speakers_stats(self):
        """두 화자 통계 계산"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="A",
                start=0.0,
                end=6.0,
            ),
            MinutesSegment(
                speaker_id="SPEAKER_01",
                speaker_name="Speaker 2",
                text="B",
                start=6.0,
                end=10.0,
            ),
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=10.0)
        assert len(stats) == 2
        sp0 = next(s for s in stats if s.speaker_id == "SPEAKER_00")
        sp1 = next(s for s in stats if s.speaker_id == "SPEAKER_01")
        assert sp0.total_speaking_time == pytest.approx(6.0)
        assert sp1.total_speaking_time == pytest.approx(4.0)
        assert sp0.speaking_ratio == pytest.approx(60.0)
        assert sp1.speaking_ratio == pytest.approx(40.0)

    def test_unknown_speaker_excluded_from_stats(self):
        """speaker_id=None(Unknown Speaker)은 통계에서 제외"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id=None,
                speaker_name="Unknown Speaker",
                text="X",
                start=0.0,
                end=5.0,
            ),
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="Y",
                start=5.0,
                end=10.0,
            ),
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=10.0)
        # Unknown Speaker는 통계에서 제외
        speaker_ids = [s.speaker_id for s in stats]
        assert None not in speaker_ids
        assert "SPEAKER_00" in speaker_ids

    def test_zero_total_duration_ratio_is_zero(self):
        """total_duration=0이면 speaking_ratio=0.0 (ZeroDivision 방지)"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="A",
                start=0.0,
                end=0.0,
            )
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=0.0)
        assert stats[0].speaking_ratio == 0.0

    def test_segment_count_accumulates(self):
        """같은 화자의 세그먼트 수 합산"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="A",
                start=0.0,
                end=5.0,
            ),
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="B",
                start=10.0,
                end=15.0,
            ),
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=20.0)
        assert stats[0].segment_count == 2

    def test_only_unknown_speakers_returns_empty_stats(self):
        """Unknown Speaker만 있을 때 통계 빈 리스트 반환"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id=None,
                speaker_name="Unknown Speaker",
                text="알 수 없음",
                start=0.0,
                end=5.0,
            )
        ]
        stats = formatter.calculate_speaker_stats(segs, total_duration=5.0)
        # Unknown Speaker만 있으면 통계는 빈 리스트
        assert stats == []


# ---------------------------------------------------------------------------
# MinutesFormatter.to_markdown() 테스트
# ---------------------------------------------------------------------------


class TestToMarkdown:
    """to_markdown(): REQ-MIN-003 마크다운 형식 출력"""

    def test_empty_segments_returns_empty_string(self):
        """세그먼트 없으면 빈 문자열"""
        from backend.pipeline.minutes_formatter import MinutesFormatter

        formatter = MinutesFormatter()
        result = formatter.to_markdown([])
        assert result == ""

    def test_markdown_format_single_segment(self):
        """단일 세그먼트: **[HH:MM:SS] Speaker N**: text 형식"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="안녕하세요.",
                start=0.0,
                end=5.0,
            )
        ]
        result = formatter.to_markdown(segs)
        assert "**[00:00:00] Speaker 1**" in result
        assert "안녕하세요." in result

    def test_markdown_time_format_hours_minutes_seconds(self):
        """시간 형식: HH:MM:SS"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="테스트",
                start=3661.0,  # 1시간 1분 1초
                end=3670.0,
            )
        ]
        result = formatter.to_markdown(segs)
        assert "[01:01:01]" in result

    def test_markdown_multiple_segments(self):
        """여러 세그먼트 줄바꿈 구분"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id="SPEAKER_00",
                speaker_name="Speaker 1",
                text="첫 번째",
                start=0.0,
                end=5.0,
            ),
            MinutesSegment(
                speaker_id="SPEAKER_01",
                speaker_name="Speaker 2",
                text="두 번째",
                start=5.0,
                end=10.0,
            ),
        ]
        result = formatter.to_markdown(segs)
        assert "Speaker 1" in result
        assert "Speaker 2" in result
        assert "\n" in result

    def test_markdown_unknown_speaker_displayed(self):
        """Unknown Speaker도 마크다운에 포함"""
        from backend.pipeline.minutes_formatter import MinutesFormatter
        from backend.schemas.minutes import MinutesSegment

        formatter = MinutesFormatter()
        segs = [
            MinutesSegment(
                speaker_id=None,
                speaker_name="Unknown Speaker",
                text="알 수 없음",
                start=0.0,
                end=5.0,
            )
        ]
        result = formatter.to_markdown(segs)
        assert "Unknown Speaker" in result
        assert "알 수 없음" in result
