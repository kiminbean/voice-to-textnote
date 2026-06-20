"""
Advanced Audio Enhancement Service Unit Tests
"""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import backend.services.audio_enhancement_service as audio_enhancement_module
from backend.schemas.audio_enhancement import (
    AudioEnhancementRequest,
    AudioQualityScore,
    EnhancementMode,
    NoiseReductionLevel,
    VoiceEnhancementMode,
)
from backend.services.audio_enhancement_service import AudioEnhancementService


class TestAudioEnhancementService:
    """AudioEnhancementService 단위 테스트"""

    def setup_method(self):
        """테스트 실행 전 초기화"""
        self.service = AudioEnhancementService()

    def test_service_initialization(self):
        """서비스 초기화 테스트"""
        assert self.service.sample_rate == 16000
        assert self.service.noise_gate_threshold == 0.001
        assert self.service.speech_threshold == 0.1

    def test_normalize_audio(self):
        """오디오 정규화 테스트"""
        # 테스트 오디오 데이터 생성
        audio = np.array([0.5, -0.3, 0.8, -0.1, 0.0])
        normalized = self.service._normalize_audio(audio)

        # 정규화 확인 (최대값이 1.0이어야 함)
        assert np.max(np.abs(normalized)) == 1.0
        assert len(normalized) == len(audio)

    def test_normalize_audio_zero(self):
        """영값 오디오 정규화 테스트"""
        audio = np.array([0.0, 0.0, 0.0])
        normalized = self.service._normalize_audio(audio)

        # 영값은 그대로 유지
        assert np.all(normalized == 0.0)

    def test_read_audio_file_mixes_stereo_and_resamples(self, tmp_path, monkeypatch):
        """스테레오 입력을 모노로 변환하고 서비스 샘플레이트로 맞춘다."""
        input_file = tmp_path / "stereo.wav"
        input_file.write_bytes(b"audio")
        stereo_audio = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)

        monkeypatch.setattr(
            "backend.services.audio_enhancement_service.sf.read",
            lambda *_args, **_kwargs: (stereo_audio, 8000),
        )

        def fake_resample(audio, orig_sr, target_sr):
            assert orig_sr == 8000
            assert target_sr == self.service.sample_rate
            return audio + 0.1

        monkeypatch.setattr(self.service, "_resample_audio", fake_resample)

        audio, sample_rate = self.service._read_audio_file(input_file)

        assert sample_rate == self.service.sample_rate
        assert audio.dtype == np.float32
        assert np.allclose(audio, np.array([0.4, 0.8], dtype=np.float32))

    def test_read_audio_file_reraises_soundfile_errors(self, tmp_path, monkeypatch):
        """파일 읽기 실패는 호출자가 처리할 수 있도록 다시 발생시킨다."""
        input_file = tmp_path / "broken.wav"
        input_file.write_bytes(b"not-a-wav")

        def fail_read(*_args, **_kwargs):
            raise RuntimeError("decode failed")

        monkeypatch.setattr("backend.services.audio_enhancement_service.sf.read", fail_read)

        with pytest.raises(RuntimeError, match="decode failed"):
            self.service._read_audio_file(input_file)

    def test_resample_audio_returns_early_for_same_rate_or_empty_audio(self):
        """리샘플이 필요 없거나 빈 입력이면 원본 배열을 그대로 반환한다."""
        audio = np.array([0.1, 0.2], dtype=np.float32)

        assert self.service._resample_audio(audio, 16000, 16000) is audio

        empty_audio = np.array([], dtype=np.float32)
        assert self.service._resample_audio(empty_audio, 8000, 16000) is empty_audio

    def test_resample_audio_uses_linear_fallback_when_librosa_fails(self, monkeypatch):
        """librosa 리샘플 실패 시 선형 보간 폴백을 사용한다."""

        def fail_resample(*_args, **_kwargs):
            raise RuntimeError("librosa unavailable")

        monkeypatch.setattr(
            audio_enhancement_module,
            "librosa",
            SimpleNamespace(resample=fail_resample),
        )

        audio = np.array([0.0, 1.0], dtype=np.float32)
        resampled = self.service._resample_audio(audio, 2, 4)

        assert resampled.dtype == np.float32
        assert len(resampled) == 4
        assert np.allclose(resampled, np.array([0.0, 0.5, 1.0, 1.0], dtype=np.float32))

    def test_apply_noise_reduction_light(self):
        """가벼운 노이즈 제거 테스트"""
        audio = np.array([0.1, 0.001, -0.05, 0.002, 0.1])
        reduced = self.service._apply_noise_reduction(audio, "light")

        # 노이즈 영역이 감소했는지 확인
        assert reduced[1] < audio[1]  # 0.001 -> 감소된 값
        assert reduced[3] < audio[3]  # 0.002 -> 감소된 값

    def test_apply_noise_reduction_aggressive(self):
        """강력한 노이즈 제거 테스트"""
        audio = np.array([0.1, 0.001, -0.05, 0.002, 0.1])
        reduced = self.service._apply_noise_reduction(audio, "aggressive")

        # 강력한 모드일수록 더 많은 감소
        assert np.max(np.abs(reduced)) < np.max(np.abs(audio))

    def test_apply_noise_reduction_moderate_keeps_speech_and_reduces_quiet_audio(self):
        """중간 노이즈 제거는 음성 임계값 아래 샘플만 줄인다."""
        audio = np.array([0.2, 0.05], dtype=np.float32)

        reduced = self.service._apply_noise_reduction(audio, NoiseReductionLevel.MODERATE)

        assert reduced[0] == pytest.approx(0.2)
        assert reduced[1] == pytest.approx(0.045)

    def test_voice_enhancement_natural(self):
        """자연스러운 보이스 향상 테스트"""
        audio = np.array([0.1, -0.1, 0.2, -0.2, 0.3])
        enhanced = self.service._voice_enhancement(audio, "natural")

        # 향상된 오디오는 클리핑되지 않아야 함
        assert np.max(np.abs(enhanced)) <= 1.0
        assert len(enhanced) == len(audio)

    @pytest.mark.parametrize("mode", [VoiceEnhancementMode.CLEAR, VoiceEnhancementMode.BROADCAST])
    def test_voice_enhancement_filter_modes_preserve_shape_and_clip(self, mode):
        """CLEAR/BROADCAST 필터 모드는 길이를 유지하고 출력 범위를 제한한다."""
        audio = np.array([0.0, 0.4, -0.4, 0.8, -0.8], dtype=np.float32)

        enhanced = self.service._voice_enhancement(audio, mode)

        assert len(enhanced) == len(audio)
        assert np.max(np.abs(enhanced)) <= 1.0
        assert not np.allclose(enhanced, audio)

    def test_detect_voice_activity(self):
        """음성 활동 검출 테스트"""
        audio = np.array([0.1, 0.2, 0.05, 0.001, 0.3, 0.0001, 0.2])
        segments = self.service._detect_voice_activity(audio, frame_length=2)

        # 세그먼트 생성 확인
        assert len(segments) > 0
        assert all(hasattr(seg, "start_time") for seg in segments)
        assert all(hasattr(seg, "end_time") for seg in segments)
        assert all(hasattr(seg, "is_speech") for seg in segments)
        assert all(hasattr(seg, "confidence") for seg in segments)
        assert all(hasattr(seg, "rms_level") for seg in segments)

    def test_detect_voice_activity_returns_empty_for_empty_audio(self):
        """빈 오디오는 세그먼트를 생성하지 않는다."""
        assert self.service._detect_voice_activity(np.array([], dtype=np.float32)) == []

    def test_calculate_quality_scores(self):
        """오디오 품질 점수 계산 테스트"""
        original = np.array([0.1, 0.2, 0.1, 0.05])
        enhanced = np.array([0.2, 0.3, 0.15, 0.1])
        segments = [
            type("Segment", (), {"is_speech": True, "rms_level": 0.1})(),
            type("Segment", (), {"is_speech": False, "rms_level": 0.001})(),
        ]

        scores = self.service._calculate_quality_scores(original, enhanced, segments)

        # 품질 점수 객체 확인
        assert 0 <= scores.overall_score <= 1
        assert 0 <= scores.clarity_score <= 1
        assert 0 <= scores.noise_level <= 1
        assert 0 <= scores.volume_level <= 1
        assert 0 <= scores.voice_activity_ratio <= 1

    def test_calculate_quality_scores_handles_single_sample_and_empty_audio(self):
        """고주파 마스크가 없거나 빈 오디오여도 유효한 점수를 반환한다."""
        single_sample_scores = self.service._calculate_quality_scores(
            np.array([0.2], dtype=np.float32),
            np.array([0.2], dtype=np.float32),
            [],
        )
        empty_scores = self.service._calculate_quality_scores(
            np.array([], dtype=np.float32),
            np.array([], dtype=np.float32),
            [],
        )

        assert single_sample_scores.clarity_score == 0.0
        assert empty_scores.clarity_score == 0.0
        assert empty_scores.volume_level == 0.0

    def test_extract_speech_segments(self):
        """순수 음성 추출 테스트"""
        audio = np.array([0.1, 0.2, 0.3, 0.01, 0.02, 0.03])
        segments = [
            type("Segment", (), {"is_speech": True, "start_time": 0.0, "end_time": 2.0 / 16000})(),
            type(
                "Segment",
                (),
                {"is_speech": False, "start_time": 2.0 / 16000, "end_time": 4.0 / 16000},
            )(),
            type(
                "Segment",
                (),
                {"is_speech": True, "start_time": 4.0 / 16000, "end_time": 6.0 / 16000},
            )(),
        ]

        extracted = self.service._extract_speech_segments(audio, segments)

        # 음성 세그먼트만 추출되었는지 확인
        assert len(extracted) > 0
        assert np.array_equal(extracted, np.concatenate([audio[:2], audio[4:]]))

    def test_extract_speech_segments_returns_original_when_no_speech_detected(self):
        """음성 세그먼트가 없으면 안전하게 원본 오디오를 반환한다."""
        audio = np.array([0.01, 0.02, 0.03], dtype=np.float32)
        segments = [
            type("Segment", (), {"is_speech": False, "start_time": 0.0, "end_time": 3.0 / 16000})()
        ]

        extracted = self.service._extract_speech_segments(audio, segments)

        assert extracted is audio

    @pytest.mark.asyncio
    async def test_enhance_audio_integration(self):
        """오디오 향상 통합 테스트"""
        # 임시 오디오 파일 생성
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            # 간단한 오디오 데이터 생성
            audio_data = np.array([0.1, -0.1, 0.2, -0.2, 0.3, -0.3])
            import soundfile as sf

            sf.write(temp_file.name, audio_data, 16000)
            temp_file_path = Path(temp_file.name)

        try:
            from backend.schemas.audio_enhancement import AudioEnhancementRequest

            request = AudioEnhancementRequest(
                enhancement_mode="enhanced",
                noise_reduction_level="moderate",
                voice_enhancement="natural",
                extract_speech_only=False,
            )

            result = await self.service.enhance_audio(temp_file_path, request)

            # 결과 객체 확인
            assert result.enhanced_file_size > 0
            assert result.processing_time_seconds >= 0
            assert 0 <= result.compression_ratio
            assert result.quality_scores.overall_score >= 0
            assert result.quality_scores.overall_score <= 1
            assert len(result.segments) > 0

        finally:
            # 임시 파일 삭제
            if temp_file_path.exists():
                temp_file_path.unlink()

    @pytest.mark.asyncio
    async def test_enhance_audio_music_mode_skips_noise_reduction_and_emits_warnings(
        self,
        tmp_path,
        monkeypatch,
    ):
        """음악 중심 모드는 노이즈 제거를 건너뛰고 위험 조건 경고를 반환한다."""
        input_file = tmp_path / "tiny.wav"
        input_file.write_bytes(b"x")
        audio = np.array([0.3, 0.2, 0.1, 0.0], dtype=np.float32)
        calls = {"noise": 0, "voice": 0, "resample": 0}

        monkeypatch.setattr(self.service, "_read_audio_file", lambda _path: (audio, 16000))

        def fail_noise(*_args, **_kwargs):
            calls["noise"] += 1
            raise AssertionError("noise reduction should be skipped")

        def fake_voice(processed_audio, mode):
            calls["voice"] += 1
            assert mode == VoiceEnhancementMode.CLEAR
            return processed_audio

        def fake_resample(processed_audio, orig_sr, target_sr):
            calls["resample"] += 1
            assert (orig_sr, target_sr) == (16000, 8000)
            return processed_audio[:2]

        def fake_write(output_file, _processed_audio, _sample_rate):
            Path(output_file).write_bytes(b"x" * 16)

        monkeypatch.setattr(self.service, "_apply_noise_reduction", fail_noise)
        monkeypatch.setattr(self.service, "_voice_enhancement", fake_voice)
        monkeypatch.setattr(self.service, "_resample_audio", fake_resample)
        monkeypatch.setattr(
            self.service,
            "_calculate_quality_scores",
            lambda *_args: AudioQualityScore(
                overall_score=0.4,
                clarity_score=0.2,
                noise_level=0.5,
                volume_level=0.5,
                voice_activity_ratio=0.25,
            ),
        )
        monkeypatch.setattr("backend.services.audio_enhancement_service.sf.write", fake_write)

        result = await self.service.enhance_audio(
            input_file,
            AudioEnhancementRequest(
                enhancement_mode=EnhancementMode.MUSIC_FOCUSED,
                voice_enhancement=VoiceEnhancementMode.CLEAR,
                extract_speech_only=True,
                target_sample_rate=8000,
            ),
        )

        assert calls == {"noise": 0, "voice": 1, "resample": 1}
        assert result.enhanced_file_size == 16
        assert result.compression_ratio == pytest.approx(0.062)
        assert result.metadata["original_sample_rate"] == 8000
        assert result.warnings == [
            "오디오 품질이 낮습니다. 원본 오디오 품질을 확인해 주세요.",
            "음성이 매우 적게 검출되었습니다.",
            "처리 후 파일 크기가 크게 증가했습니다.",
        ]

    @pytest.mark.asyncio
    async def test_enhance_audio_clean_mode_skips_voice_enhancement(self, tmp_path, monkeypatch):
        """클린 모드는 보이스 향상을 건너뛰고 노이즈 제거만 적용한다."""
        input_file = tmp_path / "clean.wav"
        input_file.write_bytes(b"x" * 20)
        audio = np.array([0.2, 0.1], dtype=np.float32)
        calls = {"noise": 0}

        monkeypatch.setattr(self.service, "_read_audio_file", lambda _path: (audio, 16000))

        def fake_noise(processed_audio, level):
            calls["noise"] += 1
            assert level == NoiseReductionLevel.LIGHT
            return processed_audio * 0.5

        def fail_voice(*_args, **_kwargs):
            raise AssertionError("voice enhancement should be skipped")

        def fake_write(output_file, _processed_audio, _sample_rate):
            Path(output_file).write_bytes(b"x" * 10)

        monkeypatch.setattr(self.service, "_apply_noise_reduction", fake_noise)
        monkeypatch.setattr(self.service, "_voice_enhancement", fail_voice)
        monkeypatch.setattr("backend.services.audio_enhancement_service.sf.write", fake_write)

        result = await self.service.enhance_audio(
            input_file,
            AudioEnhancementRequest(
                enhancement_mode=EnhancementMode.CLEAN,
                noise_reduction_level=NoiseReductionLevel.LIGHT,
                normalize_audio=False,
            ),
        )

        assert calls["noise"] == 1
        assert result.enhanced_file_size == 10
        assert result.warnings == []

    def test_audio_quality_score_validation(self):
        """오디오 품질 점수 범위 검증"""
        from backend.schemas.audio_enhancement import AudioQualityScore

        score = AudioQualityScore(
            overall_score=0.8,
            clarity_score=0.7,
            noise_level=0.2,
            volume_level=0.9,
            voice_activity_ratio=0.75,
        )

        assert 0 <= score.overall_score <= 1
        assert 0 <= score.clarity_score <= 1
        assert 0 <= score.noise_level <= 1
        assert 0 <= score.volume_level <= 1
        assert 0 <= score.voice_activity_ratio <= 1
