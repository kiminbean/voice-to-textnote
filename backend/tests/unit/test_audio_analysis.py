"""
오디오 분석 엔진 테스트
"""

import os
import tempfile
import wave

import pytest

from backend.ml.audio_analysis_engine import (
    AudioAnalysisResult,
    _evaluate_quality,
    analyze_audio,
)


def _create_test_wav(
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    frequency: int = 440,
) -> str:
    """테스트용 WAV 파일 생성"""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    n_frames = int(duration_seconds * sample_rate)
    import math
    import struct

    with wave.open(tmp_path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)

        frames = []
        for i in range(n_frames):
            value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames.append(struct.pack("<h", value))
        wf.writeframes(b"".join(frames))

    return tmp_path


def _create_silence_wav(
    duration_seconds: float = 2.0,
    sample_rate: int = 16000,
) -> str:
    """무음 테스트용 WAV 파일 생성"""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    n_frames = int(duration_seconds * sample_rate)

    with wave.open(tmp_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 무음 (모든 샘플이 0)
        wf.writeframes(b"\x00\x00" * n_frames)

    return tmp_path


class TestAnalyzeAudio:
    """analyze_audio 함수 테스트"""

    def test_basic_analysis(self):
        """기본 오디오 분석"""
        path = _create_test_wav(duration_seconds=1.0)
        try:
            result = analyze_audio(path)
            assert isinstance(result, AudioAnalysisResult)
            assert result.duration_seconds >= 0.9
            assert result.sample_rate == 16000
            assert result.channels == 1
            assert result.file_size_bytes > 0
            assert result.filename.endswith(".wav")
        finally:
            os.unlink(path)

    def test_format_detection(self):
        """포맷 감지"""
        path = _create_test_wav()
        try:
            result = analyze_audio(path)
            assert result.format == "WAV"
        finally:
            os.unlink(path)

    def test_volume_analysis(self):
        """볼륨 분석"""
        path = _create_test_wav()
        try:
            result = analyze_audio(path)
            assert result.max_dbfs is not None
            assert result.avg_dbfs is not None
            assert result.rms_dbfs is not None
            assert result.rms_dbfs < 0
        finally:
            os.unlink(path)

    def test_silence_detection(self):
        """무음 구간 감지"""
        # 1초 사인파 + 1초 무음 + 1초 사인파 생성은 복잡하므로
        # 무음 파일로 테스트
        path = _create_silence_wav(duration_seconds=2.0)
        try:
            result = analyze_audio(
                path,
                include_silence_detection=True,
                silence_threshold_db=-30.0,
            )
            assert result.silence_ratio is not None
            # 무음 파일이므로 높은 무음 비율
            assert result.silence_ratio >= 0.5
        finally:
            os.unlink(path)

    def test_silence_disabled(self):
        """무음 감지 비활성화"""
        path = _create_test_wav()
        try:
            result = analyze_audio(path, include_silence_detection=False)
            assert result.silence_segments == []
            assert result.silence_ratio is None
        finally:
            os.unlink(path)

    def test_invalid_file(self):
        """잘못된 파일 처리"""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(b"not a real audio file")
        tmp.close()
        try:
            with pytest.raises(ValueError, match="오디오 파일 로드 실패"):
                analyze_audio(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_nonexistent_file(self):
        """존재하지 않는 파일"""
        with pytest.raises((FileNotFoundError, ValueError)):
            analyze_audio("/nonexistent/path/audio.wav")


class TestEvaluateQuality:
    """_evaluate_quality 함수 테스트"""

    def test_high_quality(self):
        """높은 품질 평가"""
        from unittest.mock import MagicMock

        audio = MagicMock()
        score, issues, recommendation = _evaluate_quality(
            audio=audio,
            duration_seconds=30.0,
            sample_rate=44100,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )
        assert score >= 0.8
        assert len(issues) == 0
        assert "적합" in recommendation

    def test_low_volume(self):
        """낮은 볼륨 감지"""
        from unittest.mock import MagicMock

        audio = MagicMock()
        _score, issues, _recommendation = _evaluate_quality(
            audio=audio,
            duration_seconds=30.0,
            sample_rate=44100,
            channels=1,
            avg_dbfs=-35.0,
            silence_ratio=0.1,
        )
        assert any("볼륨" in issue for issue in issues)

    def test_low_sample_rate(self):
        """낮은 샘플레이트 감지"""
        from unittest.mock import MagicMock

        audio = MagicMock()
        _score, issues, _recommendation = _evaluate_quality(
            audio=audio,
            duration_seconds=30.0,
            sample_rate=8000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )
        assert any("샘플레이트" in issue for issue in issues)

    def test_very_low_sample_rate_penalized_more(self):
        """8kHz 미만 샘플레이트는 별도 중대 이슈로 평가"""
        from unittest.mock import MagicMock

        audio = MagicMock()
        score, issues, _recommendation = _evaluate_quality(
            audio=audio,
            duration_seconds=30.0,
            sample_rate=7000,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.1,
        )
        assert score <= 0.6
        assert any("크게 저하" in issue for issue in issues)

    def test_high_silence_ratio(self):
        """높은 무음 비율 감지"""
        from unittest.mock import MagicMock

        audio = MagicMock()
        _score, issues, _recommendation = _evaluate_quality(
            audio=audio,
            duration_seconds=60.0,
            sample_rate=44100,
            channels=1,
            avg_dbfs=-15.0,
            silence_ratio=0.8,
        )
        assert any("무음" in issue for issue in issues)
