"""
오디오 청크 관리자 단위 테스트
테스트 대상: backend.pipeline.chunk_manager
REQ-STT-018: 30분 초과 오디오 청크 분할 처리
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.pipeline.chunk_manager import (
    AudioChunk,
    _logprob_to_confidence,
    merge_segments,
    split_audio,
)

# ---------------------------------------------------------------------------
# _logprob_to_confidence 테스트
# ---------------------------------------------------------------------------


class TestLogprobToConfidence:
    """_logprob_to_confidence 함수 테스트"""

    def test_converts_negative_logprob_to_confidence(self):
        """음수 logprob을 confidence로 변환 검증"""
        # Act & Assert
        assert _logprob_to_confidence(-0.5) == pytest.approx(0.6065, 0.001)  # exp(-0.5)
        assert _logprob_to_confidence(-1.0) == pytest.approx(0.3679, 0.001)  # exp(-1.0)
        assert _logprob_to_confidence(-2.0) == pytest.approx(0.1353, 0.001)  # exp(-2.0)

    def test_clamps_confidence_to_valid_range(self):
        """confidence가 [0, 1] 범위로 클리핑되는지 검증"""
        # Act & Assert
        assert _logprob_to_confidence(0) == 1.0  # exp(0) = 1
        assert _logprob_to_confidence(10) == 1.0  # 큰 값도 1로 클리핑
        # 매 작은 값은 0에 매우 근접 (부동소수점 정밀도로 인해 0이 아닐 수 있음)
        assert _logprob_to_confidence(-100) < 0.0001  # 실제로 0에 가까운지 확인

    def test_returns_zero_for_very_negative_logprob(self):
        """매우 부정적인 logprob가 0에 근접한 값을 반환하는지 검증"""
        # Act & Assert
        result = _logprob_to_confidence(-10)
        # exp(-10) ≈ 0.0000454
        assert result < 0.00005  # 0에 매우 근접한지 확인
        assert result > 0.00004  # 너무 작지 않은지 확인


# ---------------------------------------------------------------------------
# split_audio 테스트
# ---------------------------------------------------------------------------


class TestSplitAudio:
    """split_audio 함수 테스트"""

    @patch("backend.pipeline.chunk_manager.AudioSegment")
    @patch("backend.pipeline.chunk_manager.normalize_audio")
    def test_returns_empty_list_for_short_audio(self, mock_normalize, mock_audio_segment):
        """짧은 오디오는 분할하지 않고 빈 리스트 반환 검증"""
        # Arrange
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 1000  # 1초 (chunk_duration_ms=1800000)
        mock_audio_segment.from_file.return_value = mock_audio
        mock_normalize.return_value = mock_audio

        # Act
        result = split_audio("test.wav", chunk_duration_ms=1800000, overlap_ms=5000)

        # Assert
        assert result == []
        mock_audio_segment.from_file.assert_called_once()

    @patch("backend.pipeline.chunk_manager.AudioSegment")
    @patch("backend.pipeline.chunk_manager.normalize_audio")
    @patch("backend.pipeline.chunk_manager.tempfile.mkdtemp")
    def test_splits_audio_into_chunks(self, mock_mkdtemp, mock_normalize, mock_audio_segment):
        """오디오를 청크로 분할 검증"""
        # Arrange
        mock_temp_dir = "/tmp/test_chunks"
        mock_mkdtemp.return_value = mock_temp_dir

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 3600000  # 60분
        mock_audio.__getitem__.return_value = mock_audio  # slicing

        mock_audio_segment.from_file.return_value = mock_audio
        mock_normalize.return_value = mock_audio

        # Act
        result = split_audio(
            "test.wav",
            chunk_duration_ms=1800000,  # 30분
            overlap_ms=5000,  # 5초
            output_dir=mock_temp_dir,
        )

        # Assert
        assert len(result) == 2  # 60분 / 30분 = 2 chunks
        assert result[0].index == 0
        assert result[0].start_ms == 0
        assert result[0].overlap_ms == 0  # 첫 청크는 오버랩 없음

        assert result[1].index == 1
        assert result[1].start_ms == 1800000  # 30분 후 시작
        assert result[1].overlap_ms == 5000

    @patch("backend.pipeline.chunk_manager.AudioSegment")
    @patch("backend.pipeline.chunk_manager.normalize_audio")
    @patch("backend.pipeline.chunk_manager.tempfile.mkdtemp")
    def test_creates_temp_dir_when_not_specified(self, mock_mkdtemp, mock_normalize, mock_audio_segment):
        """output_dir이 지정되지 않으면 임시 디렉토리 생성 검증"""
        # Arrange
        mock_temp_dir = "/tmp/auto_chunks"
        mock_mkdtemp.return_value = mock_temp_dir

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 3600000
        mock_audio.__getitem__.return_value = mock_audio
        mock_audio_segment.from_file.return_value = mock_audio
        mock_normalize.return_value = mock_audio

        # Act
        split_audio(
            "test.wav",
            chunk_duration_ms=1800000,
            overlap_ms=5000,
        )

        # Assert
        mock_mkdtemp.assert_called_once()

    @patch("backend.pipeline.chunk_manager.AudioSegment")
    @patch("backend.pipeline.chunk_manager.normalize_audio")
    def test_normalizes_each_chunk(self, mock_normalize, mock_audio_segment):
        """각 청크 정규화 검증"""
        # Arrange
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 3600000
        mock_audio.__getitem__.return_value = mock_audio
        mock_audio_segment.from_file.return_value = mock_audio
        mock_normalize.return_value = mock_audio

        # Act
        split_audio("test.wav", chunk_duration_ms=1800000, overlap_ms=5000)

        # Assert
        # 2개 청크 생성, 각각 정규화
        assert mock_normalize.call_count == 2

    @patch("backend.pipeline.chunk_manager.AudioSegment")
    @patch("backend.pipeline.chunk_manager.normalize_audio")
    def test_exports_chunks_as_wav(self, mock_normalize, mock_audio_segment):
        """청크를 WAV 파일로 내보내기 검증"""
        # Arrange
        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 3600000
        mock_audio.__getitem__.return_value = mock_audio
        mock_audio_segment.from_file.return_value = mock_audio
        mock_normalize.return_value = mock_audio

        # Act
        split_audio(
            "test.wav",
            chunk_duration_ms=1800000,
            overlap_ms=5000,
            output_dir="/tmp/test",
        )

        # Assert
        assert mock_audio.export.call_count == 2  # 2개 청크
        # 첫 번째 export 호출 확인
        first_call = mock_audio.export.call_args_list[0]
        assert "format" in first_call[1]
        assert first_call[1]["format"] == "wav"


# ---------------------------------------------------------------------------
# merge_segments 테스트
# ---------------------------------------------------------------------------


class TestMergeSegments:
    """merge_segments 함수 테스트"""

    def test_merges_segments_from_single_chunk(self):
        """단일 청크 세그먼트 병합 검증"""
        # Arrange
        chunk = AudioChunk(
            index=0,
            file_path=Path("/tmp/chunk_0000.wav"),
            start_ms=0,
            end_ms=30000,
            overlap_ms=0,
        )
        raw_segments = [
            {"start": 0.0, "end": 5.0, "text": "Hello world", "avg_logprob": -0.5},
            {"start": 5.0, "end": 10.0, "text": "Test segment", "avg_logprob": -0.8},
        ]

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        assert len(result) == 2
        assert result[0].id == 0
        assert result[0].start == 0.0
        assert result[0].end == 5.0
        assert result[0].text == "Hello world"
        assert result[0].confidence == pytest.approx(0.6065, 0.001)

    def test_adjusts_timestamps_for_chunk_offset(self):
        """청크 오프셋만큼 타임스탬프 조정 검증"""
        # Arrange
        chunk = AudioChunk(
            index=1,
            file_path=Path("/tmp/chunk_0001.wav"),
            start_ms=1800000,  # 30분
            end_ms=3600000,
            overlap_ms=5000,
        )
        raw_segments = [
            {"start": 6.0, "end": 11.0, "text": "Continued", "avg_logprob": -0.5}
        ]  # 오버랩 영역(5초) 이후

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        assert len(result) == 1
        assert result[0].start == 1806.0  # 1800 + 6
        assert result[0].end == 1811.0  # 1800 + 11

    def test_filters_overlap_segments_in_subsequent_chunks(self):
        """오버랩 영역 세그먼트 필터링 검증"""
        # Arrange
        chunk = AudioChunk(
            index=1,  # 두 번째 청크
            file_path=Path("/tmp/chunk_0001.wav"),
            start_ms=1800000,
            end_ms=3600000,
            overlap_ms=5000,  # 5초 오버랩
        )
        raw_segments = [
            {"start": 0.0, "end": 3.0, "text": "Overlap segment", "avg_logprob": -0.5},
            {"start": 6.0, "end": 10.0, "text": "New segment", "avg_logprob": -0.5},
        ]

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        # 첫 번째 세그먼트(0-3초)는 오버랩 영역(0-5초) 내에 있으므로 제외
        assert len(result) == 1
        assert result[0].text == "New segment"
        assert result[0].start == 1806.0  # 1800 + 6

    def test_skips_empty_text_segments(self):
        """빈 텍스트 세그먼트 건너뜀 검증"""
        # Arrange
        chunk = AudioChunk(
            index=0,
            file_path=Path("/tmp/chunk_0000.wav"),
            start_ms=0,
            end_ms=30000,
            overlap_ms=0,
        )
        raw_segments = [
            {"start": 0.0, "end": 5.0, "text": "Valid segment", "avg_logprob": -0.5},
            {"start": 5.0, "end": 10.0, "text": "   ", "avg_logprob": -0.5},  # 공백
            {"start": 10.0, "end": 15.0, "text": "", "avg_logprob": -0.5},  # 빈 문자열
        ]

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        assert len(result) == 1
        assert result[0].text == "Valid segment"

    def test_generates_sequential_global_ids(self):
        """순차적 전역 ID 생성 검증"""
        # Arrange
        chunk1 = AudioChunk(
            index=0,
            file_path=Path("/tmp/chunk_0000.wav"),
            start_ms=0,
            end_ms=30000,
            overlap_ms=0,
        )
        chunk2 = AudioChunk(
            index=1,
            file_path=Path("/tmp/chunk_0001.wav"),
            start_ms=30000,
            end_ms=60000,
            overlap_ms=5000,
        )
        raw_segments1 = [{"start": 0.0, "end": 5.0, "text": "First", "avg_logprob": -0.5}]
        raw_segments2 = [
            {"start": 6.0, "end": 11.0, "text": "Second", "avg_logprob": -0.5}
        ]  # 오버랩(5초) 이후

        # Act
        result = merge_segments([
            (chunk1, raw_segments1),
            (chunk2, raw_segments2),
        ])

        # Assert
        assert len(result) == 2
        assert result[0].id == 0
        assert result[1].id == 1

    def test_handles_missing_avg_logprob(self):
        """avg_logprob가 없을 때 confidence 기본값 처리 검증"""
        # Arrange
        chunk = AudioChunk(
            index=0,
            file_path=Path("/tmp/chunk_0000.wav"),
            start_ms=0,
            end_ms=30000,
            overlap_ms=0,
        )
        raw_segments = [{"start": 0.0, "end": 5.0, "text": "No logprob"}]  # avg_logprob 없음

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        assert len(result) == 1
        assert result[0].confidence == 0.0  # 기본값

    def test_rounds_timestamps_and_confidence(self):
        """타임스탬프와 confidence 반올림 검증"""
        # Arrange
        chunk = AudioChunk(
            index=0,
            file_path=Path("/tmp/chunk_0000.wav"),
            start_ms=0,
            end_ms=30000,
            overlap_ms=0,
        )
        raw_segments = [
            {
                "start": 0.1234567,
                "end": 5.9876543,
                "text": "Test",
                "avg_logprob": -0.5,
            }
        ]

        # Act
        result = merge_segments([(chunk, raw_segments)])

        # Assert
        assert len(result) == 1
        assert result[0].start == round(0.1234567, 3)
        assert result[0].end == round(5.9876543, 3)
        assert result[0].confidence == round(_logprob_to_confidence(-0.5), 4)
