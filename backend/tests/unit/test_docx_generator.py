"""
SPEC-EXPORT-002: DOCX 생성기 단위 테스트
"""

import pytest
from backend.pipeline.docx_generator import MinutesDOCXGenerator


@pytest.fixture
def sample_minutes():
    return {
        "task_id": "test-123",
        "segments": [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "안녕하세요 회의를 시작하겠습니다."},
            {"speaker": "SPEAKER_01", "start": 5.5, "end": 12.0, "text": "네, 오늘 안건을 설명드리겠습니다."},
            {"speaker": "SPEAKER_00", "start": 12.5, "end": 20.0, "text": "프로젝트 진행 상황을 공유해주세요."},
        ],
    }


@pytest.fixture
def sample_summary():
    return {
        "summary": "프로젝트 진행 상황 회의",
        "key_points": ["안건 공유", "진행 상황 점검"],
    }


class TestMinutesDOCXGenerator:
    def setup_method(self):
        self.generator = MinutesDOCXGenerator()

    def test_generate_basic(self, sample_minutes):
        result = self.generator.generate(sample_minutes)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # DOCX magic bytes (ZIP header)
        assert result[:2] == b"PK"

    def test_generate_with_summary(self, sample_minutes, sample_summary):
        result = self.generator.generate(sample_minutes, summary_data=sample_summary)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_no_segments_raises(self):
        with pytest.raises(ValueError, match="segments"):
            self.generator.generate({"task_id": "x"})

    def test_generate_empty_segments_raises(self):
        with pytest.raises(ValueError, match="segments"):
            self.generator.generate({"task_id": "x", "segments": []})

    def test_generate_no_summary_ok(self, sample_minutes):
        result = self.generator.generate(sample_minutes, summary_data=None)
        assert isinstance(result, bytes)

    def test_format_time(self):
        assert MinutesDOCXGenerator._format_time(0) == "00:00:00"
        assert MinutesDOCXGenerator._format_time(65) == "00:01:05"
        assert MinutesDOCXGenerator._format_time(3661) == "01:01:01"
