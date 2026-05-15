"""
SPEC-AUDIO-PREP-001 단위 테스트.

preprocess_audio() / PreprocessOptions / trim_leading_trailing_silence
의 입출력 계약을 검증한다.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

import pytest
from pydub import AudioSegment

from backend.pipeline.audio_processor import (
    PreprocessOptions,
    preprocess_audio,
    trim_leading_trailing_silence,
)


def _sine_wav_bytes(
    duration_seconds: float = 1.0,
    sample_rate: int = 44100,
    channels: int = 2,
    freq: int = 440,
) -> bytes:
    """테스트용 정현파 WAV 바이트 생성."""
    num_samples = int(sample_rate * duration_seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            sample = int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample) * channels)
    return buf.getvalue()


@pytest.fixture
def stereo_wav_44k(tmp_path: Path) -> Path:
    p = tmp_path / "stereo_44k.wav"
    p.write_bytes(_sine_wav_bytes(duration_seconds=1.0, sample_rate=44100, channels=2))
    return p


class TestPreprocessOptionsValidation:
    """옵션 유효성 검증 규칙 (안전 한계)."""

    def test_default_options_validate(self) -> None:
        PreprocessOptions().validate()  # 예외 없어야 함

    @pytest.mark.parametrize("hz", [0, -1, 9000])
    def test_invalid_high_pass_rejected(self, hz: int) -> None:
        with pytest.raises(ValueError, match="high_pass_hz"):
            PreprocessOptions(high_pass_hz=hz).validate()

    @pytest.mark.parametrize("hz", [500, 999, 17_000])
    def test_invalid_low_pass_rejected(self, hz: int) -> None:
        with pytest.raises(ValueError, match="low_pass_hz|high_pass_hz"):
            PreprocessOptions(low_pass_hz=hz).validate()

    def test_combined_high_low_pass_validate(self) -> None:
        # 두 옵션의 안전 범위가 겹치지 않도록 설계되어 있어
        # high < low가 자동 보장된다. 정상 케이스만 통과해야 함.
        PreprocessOptions(high_pass_hz=400, low_pass_hz=2000).validate()
        PreprocessOptions(high_pass_hz=80, low_pass_hz=8000).validate()

    @pytest.mark.parametrize("dbfs", [-61.0, 0.5])
    def test_target_dbfs_out_of_range_rejected(self, dbfs: float) -> None:
        with pytest.raises(ValueError, match="target_dbfs"):
            PreprocessOptions(target_dbfs=dbfs).validate()

    def test_silence_min_len_below_floor_rejected(self) -> None:
        with pytest.raises(ValueError, match="silence_min_len_ms"):
            PreprocessOptions(silence_min_len_ms=50).validate()


class TestPreprocessAudio:
    """preprocess_audio()의 실제 변환 검증."""

    def test_default_options_produce_16k_mono(self, stereo_wav_44k: Path) -> None:
        out = preprocess_audio(stereo_wav_44k)
        try:
            with wave.open(str(out), "rb") as wf:
                assert wf.getframerate() == 16000
                assert wf.getnchannels() == 1
        finally:
            out.unlink(missing_ok=True)

    def test_disable_conversion_keeps_original_rate(
        self, stereo_wav_44k: Path
    ) -> None:
        opts = PreprocessOptions(convert_to_16k_mono=False, normalize=False)
        out = preprocess_audio(stereo_wav_44k, opts)
        try:
            with wave.open(str(out), "rb") as wf:
                assert wf.getframerate() == 44100
                assert wf.getnchannels() == 2
        finally:
            out.unlink(missing_ok=True)

    def test_high_pass_attenuates_low_frequency(self, tmp_path: Path) -> None:
        # 100Hz 단일 톤 → high_pass 300Hz 적용 시 RMS가 충분히 줄어야 함
        src = tmp_path / "low_tone.wav"
        src.write_bytes(_sine_wav_bytes(sample_rate=16000, channels=1, freq=100))
        baseline = AudioSegment.from_file(str(src))
        baseline_rms = baseline.rms

        out = preprocess_audio(
            src,
            PreprocessOptions(
                convert_to_16k_mono=False,
                normalize=False,
                high_pass_hz=300,
            ),
        )
        try:
            processed = AudioSegment.from_file(str(out))
            assert processed.rms < baseline_rms * 0.5
        finally:
            out.unlink(missing_ok=True)

    def test_corrupted_file_raises_value_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.wav"
        bad.write_bytes(b"NOTAWAV\x00\x01\x02")
        with pytest.raises(ValueError):
            preprocess_audio(bad)

    def test_invalid_option_raises_before_decode(self, tmp_path: Path) -> None:
        bad = tmp_path / "irrelevant.wav"
        bad.write_bytes(b"\x00")  # 디코딩 실패할 데이터
        # 옵션 검증이 디코딩보다 먼저 실행되므로 ValueError("high_pass_hz")가 나옴
        with pytest.raises(ValueError, match="high_pass_hz"):
            preprocess_audio(bad, PreprocessOptions(high_pass_hz=9999))


class TestTrimLeadingTrailingSilence:
    """앞/뒤 무음만 제거되고 내부 무음은 보존되는지 확인."""

    def test_silent_padding_trimmed(self) -> None:
        silence = AudioSegment.silent(duration=1000)
        tone = AudioSegment(
            data=b"".join(
                struct.pack("<h", int(20000 * math.sin(2 * math.pi * 440 * i / 16000)))
                for i in range(16000)
            ),
            sample_width=2,
            frame_rate=16000,
            channels=1,
        )
        padded = silence + tone + silence  # 3초
        trimmed = trim_leading_trailing_silence(padded)
        # 앞뒤 1초 가까이 잘려나가 톤 길이(1초)에 근접해야 함
        assert len(trimmed) < len(padded)
        assert len(trimmed) >= 900  # 톤 영역은 보존

    def test_fully_silent_audio_returned_as_is(self) -> None:
        silent = AudioSegment.silent(duration=2000)
        result = trim_leading_trailing_silence(silent)
        assert len(result) == len(silent)
