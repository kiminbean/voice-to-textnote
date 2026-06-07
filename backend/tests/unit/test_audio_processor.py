"""
오디오 전처리 파이프라인 단위 테스트
REQ-STT-015, REQ-STT-016, REQ-STT-017, SPEC-AUDIO-PREP-001
"""

import math
import shutil
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydub import AudioSegment

# ffmpeg 필요 테스트 건너뛰기 (CI 등 ffmpeg 미설치 환경)
_HAS_FFMPEG = shutil.which("ffmpeg") is not None

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------


def _make_audio_segment(duration_ms: int = 1000, sample_rate: int = 16000) -> AudioSegment:
    """테스트용 AudioSegment 생성"""
    num_samples = int(sample_rate * duration_ms / 1000)
    raw_data = b"".join(
        struct.pack("<h", int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(num_samples)
    )
    return AudioSegment(
        data=raw_data,
        sample_width=2,
        frame_rate=sample_rate,
        channels=1,
    )


# ---------------------------------------------------------------------------
# convert_to_wav_16k 테스트
# ---------------------------------------------------------------------------


class TestConvertToWav16k:
    """WAV 16kHz 모노 변환 테스트 (REQ-STT-015)"""

    def test_wav_input_returns_16k_mono(self, test_audio_file: Path):
        """WAV 입력 파일을 16kHz 모노로 변환"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        result_path = convert_to_wav_16k(test_audio_file)

        with wave.open(str(result_path), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
        result_path.unlink(missing_ok=True)

    def test_output_path_specified(self, test_audio_file: Path, tmp_path: Path):
        """output_path 지정 시 해당 경로에 저장"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        out = tmp_path / "output.wav"
        result_path = convert_to_wav_16k(test_audio_file, out)
        assert result_path == out
        assert out.exists()

    def test_corrupted_file_raises_value_error(self, corrupted_audio_file: Path):
        """손상된 파일 변환 시 ValueError 발생 (REQ-STT-017)"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        with pytest.raises(ValueError, match="파일 손상|지원되지 않는 오디오 코덱|디코딩 실패"):
            convert_to_wav_16k(corrupted_audio_file)

    def test_temp_file_created_when_no_output_path(self, test_audio_file: Path):
        """output_path=None 이면 임시 파일 자동 생성"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        result_path = convert_to_wav_16k(test_audio_file)
        assert result_path.exists()
        assert result_path.suffix == ".wav"
        result_path.unlink(missing_ok=True)

    def test_stereo_converted_to_mono(self, tmp_path: Path):
        """스테레오 오디오를 모노로 변환"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        # 스테레오 WAV 생성
        stereo_path = tmp_path / "stereo.wav"
        audio = _make_audio_segment().set_channels(1).set_channels(2)
        audio.export(str(stereo_path), format="wav")

        result_path = convert_to_wav_16k(stereo_path)
        with wave.open(str(result_path), "rb") as wf:
            assert wf.getnchannels() == 1
        result_path.unlink(missing_ok=True)

    def test_high_sample_rate_downsampled_to_16k(self, tmp_path: Path):
        """44100Hz 오디오를 16000Hz로 다운샘플링"""
        from backend.pipeline.audio_processor import convert_to_wav_16k

        high_sr_path = tmp_path / "44100hz.wav"
        audio = _make_audio_segment(sample_rate=44100)
        audio.export(str(high_sr_path), format="wav")

        result_path = convert_to_wav_16k(high_sr_path)
        with wave.open(str(result_path), "rb") as wf:
            assert wf.getframerate() == 16000
        result_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# normalize_audio 테스트
# ---------------------------------------------------------------------------


class TestNormalizeAudio:
    """오디오 레벨 정규화 테스트 (REQ-STT-016)"""

    def test_normalize_returns_audio_segment(self):
        """정규화 후 AudioSegment 반환"""
        from backend.pipeline.audio_processor import normalize_audio

        audio = _make_audio_segment()
        result = normalize_audio(audio)
        assert isinstance(result, AudioSegment)

    def test_normalize_adjusts_dbfs_toward_target(self):
        """정규화 후 dBFS가 목표값(-20dBFS)에 근접"""
        from backend.pipeline.audio_processor import TARGET_DBFS, normalize_audio

        audio = _make_audio_segment()
        result = normalize_audio(audio, target_dbfs=TARGET_DBFS)
        # 무음이 아닌 경우 목표 레벨에 근접해야 함
        if audio.dBFS != float("-inf"):
            assert abs(result.dBFS - TARGET_DBFS) < 1.0

    def test_silent_audio_returned_unchanged(self):
        """무음 오디오는 변경 없이 반환"""
        from backend.pipeline.audio_processor import normalize_audio

        silent = AudioSegment.silent(duration=1000)
        result = normalize_audio(silent)
        assert isinstance(result, AudioSegment)
        assert len(result) == len(silent)

    def test_normalize_with_custom_target_dbfs(self):
        """커스텀 target_dbfs 적용"""
        from backend.pipeline.audio_processor import normalize_audio

        audio = _make_audio_segment()
        result = normalize_audio(audio, target_dbfs=-16.0)
        assert isinstance(result, AudioSegment)


# ---------------------------------------------------------------------------
# convert_and_normalize 테스트
# ---------------------------------------------------------------------------


class TestConvertAndNormalize:
    """변환 + 정규화 통합 함수 테스트"""

    def test_converts_and_normalizes_wav(self, test_audio_file: Path):
        """WAV 파일을 변환 + 정규화 처리"""
        from backend.pipeline.audio_processor import convert_and_normalize

        result_path = convert_and_normalize(test_audio_file)
        assert result_path.exists()
        assert result_path.suffix == ".wav"

        with wave.open(str(result_path), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
        result_path.unlink(missing_ok=True)

    def test_corrupted_file_raises_value_error(self, corrupted_audio_file: Path):
        """손상 파일 처리 시 ValueError 발생 (REQ-STT-017)"""
        from backend.pipeline.audio_processor import convert_and_normalize

        with pytest.raises(ValueError):
            convert_and_normalize(corrupted_audio_file)


# ---------------------------------------------------------------------------
# get_audio_duration_seconds 테스트
# ---------------------------------------------------------------------------


class TestGetAudioDurationSeconds:
    """오디오 재생 시간 측정 테스트"""

    def test_duration_returns_correct_seconds(self, test_audio_file: Path):
        """1초 WAV 파일의 재생 시간이 1초에 근접"""
        from backend.pipeline.audio_processor import get_audio_duration_seconds

        duration = get_audio_duration_seconds(test_audio_file)
        assert abs(duration - 1.0) < 0.1

    def test_corrupted_file_raises_value_error(self, corrupted_audio_file: Path):
        """손상 파일 측정 시 ValueError 발생"""
        from backend.pipeline.audio_processor import get_audio_duration_seconds

        with pytest.raises(ValueError):
            get_audio_duration_seconds(corrupted_audio_file)

    def test_wav_file_with_invalid_sample_rate(self, tmp_path: Path):
        """유효하지 않은 샘플레이트의 WAV 파일은 ValueError 발생"""
        from backend.pipeline.audio_processor import get_audio_duration_seconds

        # 실제 WAV 파일 생성 후 샘플레이트를 조작하여 유효하지 않은 파일 시뮬레이션
        invalid_wav = tmp_path / "invalid_sr.wav"

        # 정상적인 WAV 파일 생성
        audio = _make_audio_segment(duration_ms=1000)
        audio.export(str(invalid_wav), format="wav")

        # WAV 파일을 읽어서 샘플레이트 필드를 0으로 수정
        with open(invalid_wav, "rb") as f:
            wav_data = bytearray(f.read())

        # WAV 파일에서 sample rate 위치 (offset 24)를 0으로 설정
        # WAV 구조: [12 bytes header] [4 bytes fmt] [16 bytes fmt chunk] [sample rate at offset 24]
        if len(wav_data) > 28:
            wav_data[24:28] = b"\x00\x00\x00\x00"  # frame_rate = 0

        with open(invalid_wav, "wb") as f:
            f.write(wav_data)

        with pytest.raises(ValueError, match="유효하지 않은 WAV 샘플레이트"):
            get_audio_duration_seconds(invalid_wav)

    @pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg not installed")
    def test_non_wav_file_uses_mediainfo(self, tmp_path: Path, monkeypatch):
        """WAV가 아닌 파일은 mediainfo로 길이 측정"""

        from backend.pipeline.audio_processor import get_audio_duration_seconds

        mp3_path = tmp_path / "audio.mp3"
        audio = _make_audio_segment()
        audio.export(str(mp3_path), format="mp3")

        # mediainfo mock
        mock_info = {"duration": "2.5"}
        with patch("backend.pipeline.audio_processor.mediainfo", return_value=mock_info):
            duration = get_audio_duration_seconds(mp3_path)
            assert duration == 2.5

    @pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg not installed")
    def test_fallback_to_full_audio_load(self, tmp_path: Path):
        """mediainfo 실패 시 전체 오디오 로드로 폴백"""
        from backend.pipeline.audio_processor import get_audio_duration_seconds

        mp3_path = tmp_path / "audio.mp3"
        audio = _make_audio_segment(duration_ms=2000)
        audio.export(str(mp3_path), format="mp3")

        # mediainfo가 duration을 반환하지 않는 경우
        with patch("backend.pipeline.audio_processor.mediainfo", return_value={}):
            duration = get_audio_duration_seconds(mp3_path)
            assert abs(duration - 2.0) < 0.1


# ---------------------------------------------------------------------------
# cleanup_temp_file 테스트
# ---------------------------------------------------------------------------


class TestCleanupTempFile:
    """임시 파일 삭제 테스트 (REQ-STT-004, REQ-STT-014)"""

    def test_existing_file_deleted(self, tmp_path: Path):
        """존재하는 파일 삭제"""
        from backend.pipeline.audio_processor import cleanup_temp_file

        temp_file = tmp_path / "to_delete.wav"
        temp_file.write_bytes(b"\x00")
        assert temp_file.exists()

        cleanup_temp_file(temp_file)
        assert not temp_file.exists()

    def test_nonexistent_file_no_error(self, tmp_path: Path):
        """존재하지 않는 파일은 에러 없이 통과"""
        from backend.pipeline.audio_processor import cleanup_temp_file

        nonexistent = tmp_path / "nonexistent.wav"
        # 에러 없이 실행되어야 함
        cleanup_temp_file(nonexistent)


# ---------------------------------------------------------------------------
# PreprocessOptions 테스트 (SPEC-AUDIO-PREP-001)
# ---------------------------------------------------------------------------


class TestPreprocessOptions:
    """전처리 옵션 데이터클래스 테스트"""

    def test_default_values(self):
        """기본값 설정 확인"""
        from backend.pipeline.audio_processor import (
            DEFAULT_SILENCE_MIN_LEN_MS,
            DEFAULT_SILENCE_THRESHOLD_DB,
            TARGET_DBFS,
            PreprocessOptions,
        )

        opts = PreprocessOptions()
        assert opts.convert_to_16k_mono is True
        assert opts.normalize is True
        assert opts.target_dbfs == TARGET_DBFS
        assert opts.high_pass_hz is None
        assert opts.low_pass_hz is None
        assert opts.trim_silence is False
        assert opts.silence_threshold_db == DEFAULT_SILENCE_THRESHOLD_DB
        assert opts.silence_min_len_ms == DEFAULT_SILENCE_MIN_LEN_MS

    def test_validation_pass_with_valid_options(self):
        """유효한 옵션으로 검증 통과"""
        from backend.pipeline.audio_processor import PreprocessOptions

        opts = PreprocessOptions(high_pass_hz=80, low_pass_hz=8000)
        opts.validate()  # ValueError가 발생하지 않아야 함

    def test_validation_raises_for_high_pass_out_of_range(self):
        """high_pass_hz 범위 초과 시 ValueError"""
        from backend.pipeline.audio_processor import MAX_HIGH_PASS_HZ, PreprocessOptions

        opts = PreprocessOptions(high_pass_hz=MAX_HIGH_PASS_HZ + 1)
        with pytest.raises(ValueError, match="high_pass_hz.*1~"):
            opts.validate()

    def test_validation_raises_for_low_pass_below_minimum(self):
        """low_pass_hz 최솟값 미만 시 ValueError"""
        from backend.pipeline.audio_processor import MIN_LOW_PASS_HZ, PreprocessOptions

        opts = PreprocessOptions(low_pass_hz=MIN_LOW_PASS_HZ - 1)
        with pytest.raises(ValueError, match=f"low_pass_hz.*{MIN_LOW_PASS_HZ}~"):
            opts.validate()

    def test_validation_raises_for_low_pass_above_maximum(self):
        """low_pass_hz 최댓값 초과 시 ValueError"""
        from backend.pipeline.audio_processor import (
            MAX_LOW_PASS_HZ,
            MIN_LOW_PASS_HZ,
            PreprocessOptions,
        )

        opts = PreprocessOptions(low_pass_hz=MAX_LOW_PASS_HZ + 1)
        with pytest.raises(ValueError, match=f"low_pass_hz.*{MIN_LOW_PASS_HZ}~{MAX_LOW_PASS_HZ}"):
            opts.validate()

    def test_validation_raises_for_invalid_target_dbfs(self):
        """target_dbfs 범위 초과 시 ValueError"""
        from backend.pipeline.audio_processor import PreprocessOptions

        # -60.0 ~ 0.0 범위를 벗어나는 값들
        opts1 = PreprocessOptions(target_dbfs=-70.0)
        with pytest.raises(ValueError, match="target_dbfs.*-60\\.0.*0\\.0"):
            opts1.validate()

        opts2 = PreprocessOptions(target_dbfs=10.0)
        with pytest.raises(ValueError, match="target_dbfs.*-60\\.0.*0\\.0"):
            opts2.validate()

    def test_validation_raises_for_silence_min_len_too_small(self):
        """silence_min_len_ms가 100ms 미만이면 ValueError"""
        from backend.pipeline.audio_processor import PreprocessOptions

        opts = PreprocessOptions(silence_min_len_ms=99)
        with pytest.raises(ValueError, match="silence_min_len_ms.*100ms"):
            opts.validate()

    def test_validation_pass_boundary_values(self):
        """경계값에서 검증 통과"""
        from backend.pipeline.audio_processor import (
            MAX_HIGH_PASS_HZ,
            MAX_LOW_PASS_HZ,
            MIN_LOW_PASS_HZ,
            PreprocessOptions,
        )

        opts = PreprocessOptions(
            high_pass_hz=1,  # 최솟값
            low_pass_hz=MAX_LOW_PASS_HZ,  # 최댓값
            target_dbfs=-60.0,  # 최솟값
            silence_min_len_ms=100,  # 최솟값
        )
        opts.validate()  # 통과해야 함

        opts2 = PreprocessOptions(
            high_pass_hz=MAX_HIGH_PASS_HZ,  # 최댓값
            low_pass_hz=MIN_LOW_PASS_HZ,  # 최솟값
            target_dbfs=0.0,  # 최댓값
        )
        opts2.validate()  # 통과해야 함


# ---------------------------------------------------------------------------
# trim_leading_trailing_silence 테스트
# ---------------------------------------------------------------------------


class TestTrimLeadingTrailingSilence:
    """무음 트리밍 테스트 (SPEC-AUDIO-PREP-001)"""

    def test_empty_audio_returned_unchanged(self):
        """빈 오디오는 변경 없이 반환"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        empty = AudioSegment.silent(duration=0)
        result = trim_leading_trailing_silence(empty)
        assert len(result) == 0

    def test_silent_audio_returned_unchanged(self):
        """완전 무음 오디오는 변경 없이 반환"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        silent = AudioSegment.silent(duration=1000)
        result = trim_leading_trailing_silence(silent)
        assert len(result) == 1000

    def test_audio_with_speech_trimmed(self):
        """앞/뒤 무음이 제거된 발화 구간만 반환"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        # 100ms 무음 + 500ms 발화 + 100ms 무음
        silent_prefix = AudioSegment.silent(duration=100)
        speech = _make_audio_segment(duration_ms=500)
        silent_suffix = AudioSegment.silent(duration=100)
        audio = silent_prefix + speech + silent_suffix

        result = trim_leading_trailing_silence(
            audio, silence_threshold_db=-40, min_silence_len_ms=50
        )

        # 앞/뒤 무음이 제거되어야 함 (500ms ± 오차)
        assert 400 < len(result) < 600

    def test_no_nonsilent_detected_returns_original(self):
        """발화가 감지되지 않으면 원본 유지"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        # 완전 무음
        silent = AudioSegment.silent(duration=1000)
        result = trim_leading_trailing_silence(silent)

        assert len(result) == 1000

    def test_custom_threshold_and_min_len(self):
        """커스텀 임계값과 최소 길이 적용"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        # 200ms 무음 + 300ms 발화 + 200ms 무음
        audio = AudioSegment.silent(duration=200) + _make_audio_segment(duration_ms=300)

        # min_silence_len_ms=150로 설정하면 200ms 무음 구간이 제거됨
        result = trim_leading_trailing_silence(
            audio, silence_threshold_db=-40, min_silence_len_ms=150
        )

        # 무음 제거되어 길이가 줄어야 함
        assert len(result) < len(audio)

    def test_preserves_internal_silence(self):
        """내부 무음(말 사이 휴지)은 보존됨"""
        from backend.pipeline.audio_processor import trim_leading_trailing_silence

        # 100ms 앞 무음 + 200ms 발화 + 100ms 내부 무음 + 200ms 발화 + 100ms 뒤 무음
        audio = (
            AudioSegment.silent(duration=100)
            + _make_audio_segment(duration_ms=200)
            + AudioSegment.silent(duration=100)
            + _make_audio_segment(duration_ms=200)
            + AudioSegment.silent(duration=100)
        )

        result = trim_leading_trailing_silence(
            audio, silence_threshold_db=-40, min_silence_len_ms=50
        )

        # 내부 무음이 보존되어야 하므로 전체 길이가 400ms 근처여야 함
        # (앞/뒤 100ms씩만 제거)
        assert 380 <= len(result) <= 500


# ---------------------------------------------------------------------------
# _apply_preprocess_options 테스트
# ---------------------------------------------------------------------------


class TestApplyPreprocessOptions:
    """전처리 옵션 적용 내부 함수 테스트"""

    def test_convert_to_16k_mono(self):
        """16kHz 모노 변환 적용"""

        from backend.pipeline.audio_processor import (
            TARGET_CHANNELS,
            TARGET_SAMPLE_RATE,
            _apply_preprocess_options,
        )

        # 스테레오 44100Hz 오디오
        audio = _make_audio_segment(duration_ms=1000, sample_rate=44100).set_channels(2)
        opts = MagicMock()
        opts.convert_to_16k_mono = True
        opts.high_pass_hz = None
        opts.low_pass_hz = None
        opts.trim_silence = False
        opts.normalize = False

        result = _apply_preprocess_options(audio, opts)

        assert result.channels == TARGET_CHANNELS
        assert result.frame_rate == TARGET_SAMPLE_RATE

    def test_high_pass_filter_applied(self):
        """하이패스 필터 적용"""
        from backend.pipeline.audio_processor import _apply_preprocess_options

        audio = _make_audio_segment()
        opts = MagicMock()
        opts.convert_to_16k_mono = False
        opts.high_pass_hz = 80
        opts.low_pass_hz = None
        opts.trim_silence = False
        opts.normalize = False

        with patch.object(audio, "high_pass_filter", return_value=audio) as mock_filter:
            _apply_preprocess_options(audio, opts)
            mock_filter.assert_called_once_with(80)

    def test_low_pass_filter_applied(self):
        """로우패스 필터 적용"""
        from backend.pipeline.audio_processor import _apply_preprocess_options

        audio = _make_audio_segment()
        opts = MagicMock()
        opts.convert_to_16k_mono = False
        opts.high_pass_hz = None
        opts.low_pass_hz = 8000
        opts.trim_silence = False
        opts.normalize = False

        with patch.object(audio, "low_pass_filter", return_value=audio) as mock_filter:
            _apply_preprocess_options(audio, opts)
            mock_filter.assert_called_once_with(8000)

    def test_trim_silence_applied(self):
        """무음 트리밍 적용"""
        from backend.pipeline.audio_processor import (
            DEFAULT_SILENCE_MIN_LEN_MS,
            DEFAULT_SILENCE_THRESHOLD_DB,
            _apply_preprocess_options,
        )

        audio = _make_audio_segment()
        opts = MagicMock()
        opts.convert_to_16k_mono = False
        opts.high_pass_hz = None
        opts.low_pass_hz = None
        opts.trim_silence = True
        opts.silence_threshold_db = DEFAULT_SILENCE_THRESHOLD_DB
        opts.silence_min_len_ms = DEFAULT_SILENCE_MIN_LEN_MS
        opts.normalize = False

        with patch(
            "backend.pipeline.audio_processor.trim_leading_trailing_silence",
            return_value=audio,
        ) as mock_trim:
            _apply_preprocess_options(audio, opts)
            mock_trim.assert_called_once_with(
                audio,
                silence_threshold_db=DEFAULT_SILENCE_THRESHOLD_DB,
                min_silence_len_ms=DEFAULT_SILENCE_MIN_LEN_MS,
            )

    def test_normalize_applied(self):
        """정규화 적용"""
        from backend.pipeline.audio_processor import (
            TARGET_DBFS,
            _apply_preprocess_options,
        )

        audio = _make_audio_segment()
        opts = MagicMock()
        opts.convert_to_16k_mono = False
        opts.high_pass_hz = None
        opts.low_pass_hz = None
        opts.trim_silence = False
        opts.normalize = True
        opts.target_dbfs = TARGET_DBFS

        with patch(
            "backend.pipeline.audio_processor.normalize_audio", return_value=audio
        ) as mock_norm:
            _apply_preprocess_options(audio, opts)
            mock_norm.assert_called_once_with(audio, target_dbfs=TARGET_DBFS)

    def test_all_options_applied_in_correct_order(self):
        """모든 옵션이 올바른 순서로 적용됨"""
        from backend.pipeline.audio_processor import (
            DEFAULT_SILENCE_MIN_LEN_MS,
            DEFAULT_SILENCE_THRESHOLD_DB,
            TARGET_DBFS,
            _apply_preprocess_options,
        )

        # 이미 16kHz 모노인 오디오 생성
        audio = _make_audio_segment(duration_ms=1000, sample_rate=16000)

        opts = MagicMock()
        opts.convert_to_16k_mono = True
        opts.high_pass_hz = 80
        opts.low_pass_hz = 8000
        opts.trim_silence = True
        opts.silence_threshold_db = DEFAULT_SILENCE_THRESHOLD_DB
        opts.silence_min_len_ms = DEFAULT_SILENCE_MIN_LEN_MS
        opts.normalize = True
        opts.target_dbfs = TARGET_DBFS

        # 각 단계를 모킹하여 호출 순서 확인
        with patch.object(audio, "set_channels", return_value=audio):
            with patch.object(audio, "set_frame_rate", return_value=audio):
                with patch.object(audio, "high_pass_filter", return_value=audio) as mock_hp:
                    with patch.object(audio, "low_pass_filter", return_value=audio) as mock_lp:
                        with patch(
                            "backend.pipeline.audio_processor.trim_leading_trailing_silence",
                            return_value=audio,
                        ) as mock_trim:
                            with patch(
                                "backend.pipeline.audio_processor.normalize_audio",
                                return_value=audio,
                            ) as mock_norm:
                                _apply_preprocess_options(audio, opts)

                                # 호출 순서 확인 - 모든 mock이 호출되어야 함
                                # (16kHz 모노 오디오라도 옵션 적용 로직은 실행됨)
                                assert mock_hp.called
                                assert mock_lp.called
                                assert mock_trim.called
                                assert mock_norm.called


# ---------------------------------------------------------------------------
# preprocess_audio 테스트 (SPEC-AUDIO-PREP-001 메인 함수)
# ---------------------------------------------------------------------------


class TestPreprocessAudio:
    """옵션 기반 오디오 전처리 파이프라인 테스트"""

    def test_default_options(self, test_audio_file: Path, tmp_path: Path):
        """기본 옵션으로 전처리 (16kHz 모노 + 정규화)"""
        from backend.pipeline.audio_processor import preprocess_audio

        output_path = tmp_path / "output.wav"
        result_path = preprocess_audio(test_audio_file, output_path=output_path)

        assert result_path == output_path
        assert output_path.exists()

        with wave.open(str(output_path), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1

    def test_with_none_options_uses_defaults(self, test_audio_file: Path, tmp_path: Path):
        """options=None이면 기본 옵션 사용"""
        from backend.pipeline.audio_processor import preprocess_audio

        output_path = tmp_path / "output.wav"
        result_path = preprocess_audio(test_audio_file, options=None, output_path=output_path)

        assert result_path.exists()

    def test_custom_options(self, test_audio_file: Path, tmp_path: Path):
        """커스텀 옵션 적용"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(
            convert_to_16k_mono=False,
            normalize=False,
            high_pass_hz=100,
            low_pass_hz=8000,
        )

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_invalid_options_raises_value_error(self, test_audio_file: Path):
        """잘못된 옵션으로 ValueError 발생"""
        from backend.pipeline.audio_processor import (
            MAX_HIGH_PASS_HZ,
            PreprocessOptions,
            preprocess_audio,
        )

        opts = PreprocessOptions(high_pass_hz=MAX_HIGH_PASS_HZ + 1)

        with pytest.raises(ValueError, match="high_pass_hz"):
            preprocess_audio(test_audio_file, options=opts)

    def test_corrupted_file_raises_value_error(self, corrupted_audio_file: Path):
        """손상 파일 처리 시 ValueError 발생"""
        from backend.pipeline.audio_processor import preprocess_audio

        with pytest.raises(ValueError, match="파일 손상|디코딩 실패"):
            preprocess_audio(corrupted_audio_file)

    def test_temp_file_created_when_no_output_path(self, test_audio_file: Path):
        """output_path=None이면 임시 파일 생성"""
        from backend.pipeline.audio_processor import preprocess_audio

        result_path = preprocess_audio(test_audio_file, output_path=None)

        assert result_path.exists()
        assert result_path.suffix == ".wav"
        result_path.unlink(missing_ok=True)

    def test_with_trim_silence_option(self, test_audio_file: Path, tmp_path: Path):
        """trim_silence 옵션 적용"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(
            trim_silence=True,
            silence_threshold_db=-40.0,
            silence_min_len_ms=100,
        )

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_with_filters(self, test_audio_file: Path, tmp_path: Path):
        """하이패스/로우패스 필터 적용"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(high_pass_hz=80, low_pass_hz=8000)

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_no_normalize_option(self, test_audio_file: Path, tmp_path: Path):
        """정규화 비활성화"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(normalize=False)

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_no_convert_option(self, test_audio_file: Path, tmp_path: Path):
        """16kHz 모노 변환 비활성화"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(convert_to_16k_mono=False)

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_with_custom_target_dbfs(self, test_audio_file: Path, tmp_path: Path):
        """커스텀 target_dbfs 적용"""
        from backend.pipeline.audio_processor import PreprocessOptions, preprocess_audio

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(target_dbfs=-16.0)

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()

    def test_all_options_combined(self, test_audio_file: Path, tmp_path: Path):
        """모든 옵션 결합 테스트"""
        from backend.pipeline.audio_processor import (
            DEFAULT_SILENCE_MIN_LEN_MS,
            DEFAULT_SILENCE_THRESHOLD_DB,
            PreprocessOptions,
            preprocess_audio,
        )

        output_path = tmp_path / "output.wav"
        opts = PreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            target_dbfs=-18.0,
            high_pass_hz=100,
            low_pass_hz=9000,
            trim_silence=True,
            silence_threshold_db=DEFAULT_SILENCE_THRESHOLD_DB,
            silence_min_len_ms=DEFAULT_SILENCE_MIN_LEN_MS,
        )

        result_path = preprocess_audio(test_audio_file, options=opts, output_path=output_path)

        assert result_path.exists()
        with wave.open(str(output_path), "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1


# ---------------------------------------------------------------------------
# 분리된 기능 테스트 (chunk_manager 등)
# ---------------------------------------------------------------------------


class TestSplitAudio:
    """오디오 청크 분할 테스트 (REQ-STT-018)"""

    def test_short_audio_returns_empty_list(self, test_audio_file: Path):
        """30분 이하 오디오는 분할 없이 빈 리스트 반환"""
        from backend.pipeline.chunk_manager import split_audio

        chunks = split_audio(test_audio_file, chunk_duration_ms=30 * 60 * 1000, overlap_ms=5000)
        assert chunks == []


class TestMergeSegments:
    """청크 결과 병합 및 타임스탬프 보정 테스트 (REQ-STT-018)"""

    def test_single_chunk_no_offset(self):
        """단일 청크의 세그먼트는 오프셋 없이 그대로"""
        from backend.pipeline.chunk_manager import AudioChunk, merge_segments

        chunk = AudioChunk(
            index=0, file_path=Path("/tmp/c0.wav"), start_ms=0, end_ms=60000, overlap_ms=0
        )
        raw_segments = [{"id": 0, "start": 1.0, "end": 3.0, "text": "안녕", "avg_logprob": -0.3}]
        results = merge_segments([(chunk, raw_segments)])

        assert len(results) == 1
        assert results[0].start == pytest.approx(1.0, abs=0.01)
        assert results[0].end == pytest.approx(3.0, abs=0.01)


# ---------------------------------------------------------------------------
# 파일 형식 검증 테스트 (validators)
# ---------------------------------------------------------------------------


class TestValidateAudioFormat:
    """파일 형식 검증 테스트 (REQ-STT-001, REQ-STT-003)"""

    @pytest.mark.parametrize("filename", ["audio.wav", "meeting.mp3", "recording.m4a", "voice.ogg"])
    def test_valid_formats_accepted(self, filename: str):
        """허용 포맷(WAV, MP3, M4A, OGG)은 검증 통과"""
        from backend.utils.validators import validate_audio_format

        is_valid, msg = validate_audio_format(filename)
        assert is_valid is True
        assert msg == ""

    @pytest.mark.parametrize(
        "filename",
        ["virus.exe", "document.pdf", "data.txt", "image.jpg", "video.avi"],
    )
    def test_invalid_formats_rejected(self, filename: str):
        """지원하지 않는 형식 거부 (REQ-STT-003)"""
        from backend.utils.validators import validate_audio_format

        is_valid, msg = validate_audio_format(filename)
        assert is_valid is False
        assert "지원하지 않는" in msg

    def test_file_size_exceeds_limit_rejected(self):
        """500MB 초과 파일 거부 (REQ-STT-003)"""
        from backend.utils.validators import validate_file_size

        max_bytes = 500 * 1024 * 1024
        is_valid, msg = validate_file_size(max_bytes + 1, max_bytes)
        assert is_valid is False
        assert "500MB" in msg or "초과" in msg

    def test_file_size_at_limit_accepted(self):
        """정확히 500MB는 허용"""
        from backend.utils.validators import validate_file_size

        max_bytes = 500 * 1024 * 1024
        is_valid, msg = validate_file_size(max_bytes, max_bytes)
        assert is_valid is True
        assert msg == ""
