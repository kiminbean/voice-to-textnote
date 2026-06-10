"""
AI 기반 오디오 증강 처리 모듈

SPEC-AUDIO-ENHANCED-001: AI 기능을 이용한 고급 오디오 증강
- 노이즈 제거 (스펙트럼 분석 기반)
- 음성 강화 (레벨 균형 및 주파수 강조)
- Voice Activity Detection (VAD)
- 음질 자동 평가 및 개선 제안
"""

import asyncio
import time
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from scipy import signal
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AIEnhanceOptions:
    """AI 기반 오디오 증강 옵션"""
    enable_noise_reduction: bool = True
    enable_voice_enhancement: bool = True
    enable_vad: bool = True
    enable_quality_assessment: bool = True
    noise_reduction_strength: float = 0.7
    voice_enhancement_strength: float = 0.5
    vad_threshold: float = 0.5
    target_snr: float = 20.0
    preserve_natural_voice: bool = True
    output_format: str = "wav"

    def validate(self) -> None:
        """옵션 유효성 검증"""
        if not (0.0 <= self.noise_reduction_strength <= 1.0):
            raise ValueError("noise_reduction_strength는 0.0~1.0 사이여야 합니다.")
        if not (0.0 <= self.voice_enhancement_strength <= 1.0):
            raise ValueError("voice_enhancement_strength는 0.0~1.0 사이여야 합니다.")
        if not (0.0 <= self.vad_threshold <= 1.0):
            raise ValueError("vad_threshold는 0.0~1.0 사이여야 합니다.")
        if self.target_snr < 0:
            raise ValueError("target_snr은 0 이상이어야 합니다.")


@dataclass
class VoiceQualityScore:
    """음질 평가 점수"""
    overall_score: float  # 0-100
    clarity_score: float  # 0-1
    noise_level: float  # 0-1
    snr_db: float  # dB
    quality_grade: str  # excellent, good, fair, poor, very_poor


@dataclass
class AudioQualityEvaluation:
    """오디오 품질 평가 결과"""
    quality_assessment: VoiceQualityScore | None
    processing_details: dict[str, Any]
    warnings: list[str]


@dataclass
class EnhancementResult:
    """AI 증강 결과"""
    output_path: Path
    enhancement_id: str
    noise_reduction_applied: bool
    voice_enhancement_applied: bool
    segments_processed: int
    processing_time: float
    processing_details: dict[str, Any]
    warnings: list[str]


class AudioEnhancer:
    """AI 기반 오디오 증강 엔진"""
    
    def __init__(self):
        self.sample_rate = 16000
        self.target_channels = 1
        
    def _load_audio(self, file_path: Path) -> tuple[np.ndarray, int]:
        """오디오 파일 로드"""
        try:
            audio, sr = librosa.load(str(file_path), sr=self.sample_rate, mono=True)
            return audio, sr
        except Exception as e:
            logger.error("오디오 로딩 실패", error=str(e))
            raise ValueError(f"오디오 파일 로딩 실패: {e}")
    
    def _save_audio(self, audio: np.ndarray, output_path: Path) -> None:
        """오디오 파일 저장"""
        try:
            sf.write(str(output_path), audio, self.sample_rate)
        except Exception as e:
            logger.error("오디오 저장 실패", error=str(e))
            raise ValueError(f"오디오 파일 저장 실패: {e}")
    
    def _ai_noise_reduction(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """AI 기반 노이즈 제거 (스펙트럼 분석)"""
        if strength == 0:
            return audio
            
        logger.info("AI 노이즈 제거 시작", strength=strength)
        
        # 스펙트럼 분석
        stft = librosa.stft(audio)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # 노이즈 스펙트럼 추정 (평균 기반)
        noise_profile = np.mean(magnitude, axis=1, keepdims=True)
        
        # 스펙트럼 감쇄 적용
        spectral_subtraction = 1.0 - (strength * noise_profile / (magnitude + 1e-10))
        spectral_subtraction = np.clip(spectral_subtraction, 0.1, 1.0)
        
        # 복원
        enhanced_magnitude = magnitude * spectral_subtraction
        enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
        enhanced_audio = librosa.istft(enhanced_stft)
        
        return enhanced_audio
    
    def _voice_enhancement(self, audio: np.ndarray, strength: float) -> np.ndarray:
        """음성 강화 (주파수 강조 및 레벨 균형)"""
        if strength == 0:
            return audio
            
        logger.info("음성 강화 시작", strength=strength)
        
        # 음성 주파대 강조 (300Hz-4000Hz)
        nyquist = self.sample_rate // 2
        voice_band = [300, 4000]
        
        # 필터 설계
        b, a = signal.butter(4, [voice_band[0]/nyquist, voice_band[1]/nyquist], btype='band')
        enhanced = signal.filtfilt(b, a, audio)
        
        # 레벨 균형화
        if strength > 0:
            target_level = np.percentile(np.abs(enhanced), 95)
            current_level = np.mean(np.abs(enhanced))
            if current_level > 0:
                gain = (target_level * (0.5 + 0.5 * strength)) / current_level
                enhanced = enhanced * gain
        
        return enhanced
    
    def _voice_activity_detection(self, audio: np.ndarray, threshold: float) -> list[tuple[float, float]]:
        """Voice Activity Detection (VAD)"""
        logger.info("VAD 처리 시작", threshold=threshold)
        
        # 에너지 기반 VAD
        frame_length = 512
        hop_length = 256
        
        # 에너지 계산
        frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length)
        energy = np.sum(np.abs(frames ** 2), axis=0)
        
        # 임계값 기반 활성 탐지
        voiced_frames = energy > (threshold * np.max(energy))
        
        # 프레임 인덱스를 시간으로 변환
        voiced_segments = []
        start_idx = None
        
        for i, voiced in enumerate(voiced_frames):
            if voiced and start_idx is None:
                start_idx = i
            elif not voiced and start_idx is not None:
                start_time = start_idx * hop_length / self.sample_rate
                end_time = i * hop_length / self.sample_rate
                voiced_segments.append((start_time, end_time))
                start_idx = None
        
        # 마지막 세그먼트 처리
        if start_idx is not None:
            start_time = start_idx * hop_length / self.sample_rate
            end_time = len(voiced_frames) * hop_length / self.sample_rate
            voiced_segments.append((start_time, end_time))
        
        return voiced_segments
    
    def _quality_assessment(self, audio: np.ndarray) -> VoiceQualityScore:
        """오디오 품질 자동 평가"""
        logger.info("품질 평가 시작")
        
        # 기본 통계 계산
        signal_power = np.mean(audio ** 2)
        noise_power = np.var(audio - np.mean(audio))
        
        # SNR 계산
        snr_db = 10 * np.log10(signal_power / (noise_power + 1e-10))
        
        # 명료도 계산 (고주파 에너지 비율)
        high_freq_energy = np.sum(np.abs(audio[len(audio)//2:]) ** 2)
        total_energy = np.sum(np.abs(audio) ** 2)
        clarity = high_freq_energy / (total_energy + 1e-10)
        
        # 노이즈 레벨
        noise_level = np.sqrt(np.mean(audio ** 2))
        
        # 종합 점수 계산 (0-100)
        overall_score = min(100.0, max(0.0, snr_db * 2 + clarity * 50))
        
        # 품질 등급
        if snr_db >= 30:
            quality_grade = "excellent"
        elif snr_db >= 20:
            quality_grade = "good"
        elif snr_db >= 15:
            quality_grade = "fair"
        elif snr_db >= 10:
            quality_grade = "poor"
        else:
            quality_grade = "very_poor"
        
        return VoiceQualityScore(
            overall_score=overall_score,
            clarity_score=clarity,
            noise_level=noise_level,
            snr_db=snr_db,
            quality_grade=quality_grade,
        )
    
    def _apply_vad(self, audio: np.ndarray, segments: list[tuple[float, float]]) -> np.ndarray:
        """VAD 결과 적용 - 비활성 구간 제거"""
        if not segments:
            return audio
        
        # 비활성 구간 마스킹
        mask = np.ones(len(audio), dtype=bool)
        
        for start, end in segments:
            start_idx = int(start * self.sample_rate)
            end_idx = int(end * self.sample_rate)
            mask[start_idx:end_idx] = True
        
        return audio[mask]


def enhance_audio_with_ai(
    input_path: Path,
    options: AIEnhanceOptions
) -> EnhancementResult:
    """AI 기반 오디오 증강 메인 함수"""
    
    start_time = time.time()
    enhancer = AudioEnhancer()
    
    # 오디오 로드
    audio, sr = enhancer._load_audio(input_path)
    original_length = len(audio)
    
    processing_details = {
        "original_length": original_length,
        "sample_rate": sr,
        "processing_steps": [],
        "start_time": start_time,
    }
    
    warnings = []
    
    # Voice Activity Detection
    if options.enable_vad:
        try:
            vad_segments = enhancer._voice_activity_detection(audio, options.vad_threshold)
            processing_details["vad_segments"] = len(vad_segments)
            if vad_segments:
                audio = enhancer._apply_vad(audio, vad_segments)
                processing_details["vad_applied"] = True
        except Exception as e:
            warnings.append(f"VAD 처리 실패: {e}")
    
    # 노이즈 제거
    if options.enable_noise_reduction:
        try:
            original_audio = audio.copy()
            audio = enhancer._ai_noise_reduction(audio, options.noise_reduction_strength)
            processing_details["noise_reduction_applied"] = True
            processing_details["noise_reduction_strength"] = options.noise_reduction_strength
        except Exception as e:
            warnings.append(f"노이즈 제거 실패: {e}")
            audio = original_audio
    
    # 음성 강화
    if options.enable_voice_enhancement:
        try:
            original_audio = audio.copy()
            audio = enhancer._voice_enhancement(audio, options.voice_enhancement_strength)
            processing_details["voice_enhancement_applied"] = True
            processing_details["voice_enhancement_strength"] = options.voice_enhancement_strength
        except Exception as e:
            warnings.append(f"음성 강화 실패: {e}")
            audio = original_audio
    
    # 품질 평가
    quality_score = None
    if options.enable_quality_assessment:
        try:
            quality_score = enhancer._quality_assessment(audio)
            processing_details["quality_score"] = quality_score.overall_score
            processing_details["snr_db"] = quality_score.snr_db
        except Exception as e:
            warnings.append(f"품질 평가 실패: {e}")
    
    # 출력 파일 저장
    output_path = Path(tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name)
    enhancer._save_audio(audio, output_path)
    
    processing_time = time.time() - start_time
    processing_details["processing_time"] = processing_time
    processing_details["output_length"] = len(audio)
    
    logger.info("AI 증강 완료", 
               input_path=str(input_path),
               output_path=str(output_path),
               processing_time=processing_time,
               quality_score=quality_score.overall_score if quality_score else None)
    
    return EnhancementResult(
        output_path=output_path,
        enhancement_id=f"enh_{int(time.time())}",
        noise_reduction_applied=processing_details.get("noise_reduction_applied", False),
        voice_enhancement_applied=processing_details.get("voice_enhancement_applied", False),
        segments_processed=processing_details.get("vad_segments", 0),
        processing_time=processing_time,
        processing_details=processing_details,
        warnings=warnings,
    )


def cleanup_temp_file(file_path: Path) -> None:
    """임시 파일 안전 삭제"""
    if file_path.exists():
        file_path.unlink()
        logger.info("임시 파일 삭제", path=str(file_path))