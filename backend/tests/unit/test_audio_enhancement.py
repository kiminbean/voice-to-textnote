"""
Advanced Audio Enhancement Service Unit Tests
"""

import numpy as np
import pytest
import tempfile
from pathlib import Path

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
    
    def test_voice_enhancement_natural(self):
        """자연스러운 보이스 향상 테스트"""
        audio = np.array([0.1, -0.1, 0.2, -0.2, 0.3])
        enhanced = self.service._voice_enhancement(audio, "natural")
        
        # 향상된 오디오는 클리핑되지 않아야 함
        assert np.max(np.abs(enhanced)) <= 1.0
        assert len(enhanced) == len(audio)
    
    def test_detect_voice_activity(self):
        """음성 활동 검출 테스트"""
        audio = np.array([0.1, 0.2, 0.05, 0.001, 0.3, 0.0001, 0.2])
        segments = self.service._detect_voice_activity(audio, frame_length=2)
        
        # 세그먼트 생성 확인
        assert len(segments) > 0
        assert all(hasattr(seg, 'start_time') for seg in segments)
        assert all(hasattr(seg, 'end_time') for seg in segments)
        assert all(hasattr(seg, 'is_speech') for seg in segments)
        assert all(hasattr(seg, 'confidence') for seg in segments)
        assert all(hasattr(seg, 'rms_level') for seg in segments)
    
    def test_calculate_quality_scores(self):
        """오디오 품질 점수 계산 테스트"""
        original = np.array([0.1, 0.2, 0.1, 0.05])
        enhanced = np.array([0.2, 0.3, 0.15, 0.1])
        segments = [
            type('Segment', (), {
                'is_speech': True, 'rms_level': 0.1
            })(),
            type('Segment', (), {
                'is_speech': False, 'rms_level': 0.001
            })()
        ]
        
        scores = self.service._calculate_quality_scores(original, enhanced, segments)
        
        # 품질 점수 객체 확인
        assert 0 <= scores.overall_score <= 1
        assert 0 <= scores.clarity_score <= 1
        assert 0 <= scores.noise_level <= 1
        assert 0 <= scores.volume_level <= 1
        assert 0 <= scores.voice_activity_ratio <= 1
    
    def test_extract_speech_segments(self):
        """순수 음성 추출 테스트"""
        audio = np.array([0.1, 0.2, 0.3, 0.01, 0.02, 0.03])
        segments = [
            type('Segment', (), {
                'is_speech': True, 
                'start_time': 0.0, 
                'end_time': 2.0/16000
            })(),
            type('Segment', (), {
                'is_speech': False,
                'start_time': 2.0/16000,
                'end_time': 4.0/16000
            })(),
            type('Segment', (), {
                'is_speech': True,
                'start_time': 4.0/16000,
                'end_time': 6.0/16000
            })()
        ]
        
        extracted = self.service._extract_speech_segments(audio, segments)
        
        # 음성 세그먼트만 추출되었는지 확인
        assert len(extracted) > 0
        assert np.array_equal(extracted, np.concatenate([audio[:2], audio[4:]]))
    
    @pytest.mark.asyncio
    async def test_enhance_audio_integration(self):
        """오디오 향상 통합 테스트"""
        # 임시 오디오 파일 생성
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
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
                extract_speech_only=False
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
    
    def test_audio_quality_score_validation(self):
        """오디오 품질 점수 범위 검증"""
        from backend.schemas.audio_enhancement import AudioQualityScore
        
        score = AudioQualityScore(
            overall_score=0.8,
            clarity_score=0.7,
            noise_level=0.2,
            volume_level=0.9,
            voice_activity_ratio=0.75
        )
        
        assert 0 <= score.overall_score <= 1
        assert 0 <= score.clarity_score <= 1
        assert 0 <= score.noise_level <= 1
        assert 0 <= score.volume_level <= 1
        assert 0 <= score.voice_activity_ratio <= 1