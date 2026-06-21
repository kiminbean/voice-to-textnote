"""
오디오 분석 엔진 커버리지 추가 테스트
커버리지 부족 라인: 86-87, 204-205, 234-235
"""

import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.ml.audio_analysis_engine import (
    SilenceSegment,
    _detect_silence,
    _evaluate_quality,
    analyze_audio,
)


def _write_silent_wav(path: Path, duration_seconds: int = 6) -> Path:
    """테스트용 무음 WAV 파일을 생성한다."""
    sample_rate = 16000
    frame_count = sample_rate * duration_seconds
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return path


class TestSilenceDetection:
    """라인 86-87: 무음 감지 예외 처리"""

    def test_detect_silence_exception_returns_empty_list(self):
        """무음 감지 예외 발생 시 빈 리스트 반환"""
        mock_audio = MagicMock()

        with patch("pydub.silence.detect_silence", side_effect=Exception("Detection failed")):
            segments = _detect_silence(mock_audio)
            assert segments == []

    def test_detect_silence_negative_infinity_dbfs(self):
        """dBFS가 -inf인 segment 처리 (라인 86-87)"""
        mock_audio = MagicMock()
        mock_segment = MagicMock()
        mock_segment.dBFS = float("-inf")
        mock_audio.__getitem__ = MagicMock(return_value=mock_segment)

        with patch("pydub.silence.detect_silence") as mock_detect:
            mock_detect.return_value = [(1000, 1500)]
            segments = _detect_silence(mock_audio)

            # -inf인 경우 avg_dbfs는 None
            assert segments[0].avg_dbfs is None


class TestQualityEvaluationRms:
    """라인 204-205: RMS dBFS 계산"""

    def test_evaluate_quality_with_zero_rms(self):
        """RMS가 0인 경우 -inf 처리 (라인 204-205)"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1
        mock_audio.sample_width = 2
        mock_audio.rms = 0

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )

        # RMS가 0이어도 점수 계산됨
        assert 0.0 <= score <= 1.0

    def test_evaluate_quality_with_negative_infinity_avg_dbfs(self):
        """avg_dbfs가 -inf인 경우 처리"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1
        mock_audio.dBFS = float("-inf")
        mock_audio.rms = 1000

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            avg_dbfs=float("-inf"),
            silence_ratio=0.1,
        )

        # -inf도 점수 계산됨
        assert 0.0 <= score <= 1.0


class TestQualityEvaluationBoundary:
    """라인 234-235: 경계값 처리"""

    def test_evaluate_quality_sample_rate_boundary(self):
        """샘플레이트 경계값 테스트 (라인 234)"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 8000  # 경계값
        mock_audio.channels = 1

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=8000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )

        assert score <= 0.8  # 경계값에서 감점
        assert any("샘플레이트가 낮습니다" in issue for issue in issues)

    def test_evaluate_quality_channels_boundary(self):
        """채널 수 경계값 테스트 (라인 235)"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 3  # 경계 초과

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=3,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )

        assert score <= 0.9  # 다중 채널 감점
        assert any("채널 수가 많습니다" in issue for issue in issues)


class TestAnalyzeAudioWithSilence:
    """무음 감지 포함 분석 테스트"""

    def test_analyze_audio_with_silence_detection(self, tmp_path: Path):
        """무음 감지 포함 분석"""
        audio_path = _write_silent_wav(tmp_path / "test.wav")

        # 무음 감지 mock
        with patch("pydub.silence.detect_silence") as mock_detect:
            mock_detect.return_value = [(1000, 2000), (5000, 6000)]

            result = analyze_audio(
                audio_path,
                include_silence_detection=True,
                silence_threshold_db=-40.0,
                min_silence_duration_ms=500,
            )

        # 무음 구간 확인
        assert len(result.silence_segments) == 2
        assert result.silence_segments[0].start_ms == 1000
        assert result.silence_ratio is not None
        assert result.speech_ratio is not None

    def test_analyze_audio_without_silence_detection(self, tmp_path: Path):
        """무음 감지 제외 분석"""
        audio_path = _write_silent_wav(tmp_path / "test.wav")

        result = analyze_audio(audio_path, include_silence_detection=False)

        # 무음 감지 비활성화
        assert result.silence_segments == []
        assert result.silence_ratio is None
        assert result.speech_ratio is None


class TestAnalyzeAudioErrors:
    """오디오 분석 에러 처리 테스트"""

    @patch("pathlib.Path.stat")
    def test_analyze_audio_file_not_found(self, mock_stat):
        """파일이 존재하지 않을 때 FileNotFoundError"""
        from pathlib import Path

        mock_stat.side_effect = FileNotFoundError("File not found")

        with pytest.raises(FileNotFoundError):
            analyze_audio(Path("/nonexistent/file.mp3"))

    @patch("pydub.AudioSegment")
    @patch("pydub.utils.mediainfo")
    @patch("pathlib.Path.stat")
    def test_analyze_audio_decode_error(self, mock_stat, mock_mediainfo, mock_audio_segment):
        """오디오 디코딩 실패 시 ValueError"""
        from pydub.exceptions import CouldntDecodeError

        mock_audio_segment.from_file.side_effect = CouldntDecodeError("Decode failed")

        with (
            patch("pathlib.Path.name", return_value="test.mp3"),
            patch("pathlib.Path.suffix", ".mp3"),
            patch("pathlib.Path.__str__", return_value="test.mp3"),
        ):
            with pytest.raises(ValueError, match="오디오 파일 로드 실패"):
                analyze_audio("test.mp3")

    @patch("pydub.AudioSegment")
    @patch("pydub.utils.mediainfo")
    @patch("pathlib.Path.stat")
    def test_analyze_audio_general_exception(self, mock_stat, mock_mediainfo, mock_audio_segment):
        """일반적인 예외 발생 시 ValueError"""
        mock_audio_segment.from_file.side_effect = Exception("General error")

        with (
            patch("pathlib.Path.name", return_value="test.mp3"),
            patch("pathlib.Path.suffix", ".mp3"),
            patch("pathlib.Path.__str__", return_value="test.mp3"),
        ):
            with pytest.raises(ValueError, match="오디오 파일 로드 실패"):
                analyze_audio("test.mp3")


class TestQualityEvaluationExtremes:
    """극단적인 품질 평가 테스트"""

    def test_evaluate_quality_perfect_conditions(self):
        """완벽한 조건에서 최고 점수"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1
        mock_audio.dBFS = -15.0
        mock_audio.rms = 5000

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.05,
        )

        assert score >= 0.9
        assert len(issues) == 0
        assert "적합" in recommendation

    def test_evaluate_quality_worst_conditions(self):
        """최악 조건에서 최저 점수"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 4000  # 매우 낮음
        mock_audio.channels = 5  # 다중 채널
        mock_audio.dBFS = -50.0  # 매우 낮은 볼륨
        mock_audio.rms = 10

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=2.0,  # 짧은 녹음
            sample_rate=4000,
            channels=5,
            avg_dbfs=-50.0,
            silence_ratio=0.9,  # 90% 무음
        )

        # 점수 보정
        assert 0.0 <= score <= 0.3
        assert len(issues) > 0
        assert "품질이 낮아" in recommendation

    def test_evaluate_quality_clipping_volume(self):
        """클리핑 수준 볼륨 테스트"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1
        mock_audio.dBFS = -1.0  # 매우 높음
        mock_audio.rms = 10000

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            avg_dbfs=-1.0,
            silence_ratio=0.1,
        )

        assert score < 0.9
        assert any("클리핑" in issue for issue in issues)

    def test_evaluate_quality_ultra_short(self):
        """매우 짧은 녹음 (1초 미만)"""
        mock_audio = MagicMock()
        mock_audio.frame_rate = 16000
        mock_audio.channels = 1

        score, issues, recommendation = _evaluate_quality(
            audio=mock_audio,
            duration_seconds=0.5,
            sample_rate=16000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )

        assert score <= 0.9
        assert any("녹음이 너무 짧습니다" in issue for issue in issues)


class TestSilenceSegmentCreation:
    """SilenceSegment 생성 테스트"""

    def test_silence_segment_with_all_fields(self):
        """모든 필드가 포함된 SilenceSegment 생성"""
        segment = SilenceSegment(start_ms=1000.0, end_ms=2000.0, duration_ms=1000.0, avg_dbfs=-45.0)

        assert segment.start_ms == 1000.0
        assert segment.end_ms == 2000.0
        assert segment.duration_ms == 1000.0
        assert segment.avg_dbfs == -45.0

    def test_silence_segment_without_optional_fields(self):
        """선택적 필드 없는 SilenceSegment 생성"""
        segment = SilenceSegment(start_ms=1000.0, end_ms=2000.0, duration_ms=1000.0)

        assert segment.avg_dbfs is None
