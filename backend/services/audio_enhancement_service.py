"""
Advanced Audio Enhancement Service
AI 기반 오디오 향상 및 노이즈 제거 서비스
"""

import logging
import tempfile
import uuid
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from pydantic import BaseModel

from backend.schemas.audio_enhancement import (
    AudioEnhancementRequest,
    AudioQualityScore,
    EnhancementMode,
    EnhancementResult,
    NoiseReductionLevel,
    VoiceEnhancementMode,
)

logger = logging.getLogger(__name__)


class AudioSegment(BaseModel):
    """오디오 세그먼트 정보"""

    start_time: float
    end_time: float
    is_speech: bool
    confidence: float
    rms_level: float  # RMS 레벨 (0.0-1.0)


class AudioEnhancementService:
    """AI 기반 오디오 향장 서비스"""

    def __init__(self):
        self.sample_rate = 16000
        self.noise_gate_threshold = 0.001
        self.speech_threshold = 0.1

    def _read_audio_file(self, file_path: Path) -> tuple[np.ndarray, int]:
        """오디오 파일 읽기"""
        try:
            audio, sr = sf.read(file_path, dtype="float32", always_2d=False)
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            if sr != self.sample_rate:
                audio = self._resample_audio(audio, sr, self.sample_rate)
                sr = self.sample_rate
            return np.asarray(audio, dtype=np.float32), sr
        except Exception as e:
            logger.error("오디오 파일 읽기 실패: %s: %s", file_path, e)
            raise

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """샘플 레이트 변환. librosa 실패 시 선형 보간으로 폴백."""
        if orig_sr == target_sr or len(audio) == 0:
            return audio
        try:
            return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
        except Exception as e:
            logger.warning("librosa resample 실패, 선형 보간 사용: %s", e)
            duration = len(audio) / orig_sr
            target_len = max(1, int(round(duration * target_sr)))
            old_x = np.linspace(0.0, duration, num=len(audio), endpoint=False)
            new_x = np.linspace(0.0, duration, num=target_len, endpoint=False)
            return np.interp(new_x, old_x, audio).astype(np.float32)

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """오디오 정규화"""
        if np.max(np.abs(audio)) > 0:
            return audio / np.max(np.abs(audio))
        return audio

    def _apply_noise_reduction(self, audio: np.ndarray, level: NoiseReductionLevel) -> np.ndarray:
        """스펙트럼 가팅 노이즈 제거"""
        if level == NoiseReductionLevel.LIGHT:
            alpha = 0.95
            threshold = self.speech_threshold
        elif level == NoiseReductionLevel.MODERATE:
            alpha = 0.9
            threshold = self.speech_threshold
        else:  # AGGRESSIVE
            alpha = 0.8
            threshold = 1.0

        # 간단한 노이즈 게이트 적용
        noise_gate = np.abs(audio) > threshold
        enhanced_audio = np.where(noise_gate, audio, audio * alpha)

        return enhanced_audio

    def _voice_enhancement(self, audio: np.ndarray, mode: VoiceEnhancementMode) -> np.ndarray:
        """보이스 향상"""
        if mode == VoiceEnhancementMode.NATURAL:
            # 자연스러운 보이스 향상 - 음성 영역만 살짝 강조
            speech_mask = np.abs(audio) > self.speech_threshold
            enhanced = np.where(speech_mask, audio * 1.1, audio)

        elif mode == VoiceEnhancementMode.CLEAR:
            # 명확성 중심 - 고주파 강조
            # 간단한 고주강화 필터 적용
            high_freq = np.convolve(audio, [0.1, 0.2, 0.4, 0.2, 0.1], mode="same")
            enhanced = audio + 0.3 * high_freq

        else:  # BROADCAST
            # 방송용 - 중간 주파대 강조
            mid_freq = np.convolve(audio, [0.2, 0.6, 0.2], mode="same")
            enhanced = audio + 0.5 * mid_freq

        return np.clip(enhanced, -1.0, 1.0)

    def _detect_voice_activity(
        self, audio: np.ndarray, frame_length: int = 1024
    ) -> list[AudioSegment]:
        """음성 활동 검출 (VAD)"""
        segments = []
        num_frames = max(1, int(np.ceil(len(audio) / frame_length))) if len(audio) else 0

        for i in range(num_frames):
            start_idx = i * frame_length
            end_idx = min(start_idx + frame_length, len(audio))
            frame = audio[start_idx:end_idx]
            if len(frame) == 0:
                continue

            # 간단한 에너지 기반 VAD
            rms = float(np.sqrt(np.mean(frame**2)))
            is_speech = rms > self.speech_threshold
            confidence = min(rms / 0.5, 1.0)  # 정규화된 신뢰도

            segments.append(
                AudioSegment(
                    start_time=start_idx / self.sample_rate,
                    end_time=end_idx / self.sample_rate,
                    is_speech=bool(is_speech),
                    confidence=float(confidence),
                    rms_level=float(rms),
                )
            )

        return segments

    def _extract_speech_segments(
        self, audio: np.ndarray, segments: list[AudioSegment]
    ) -> np.ndarray:
        """순수 음성 추출"""
        speech_segments = []

        for segment in segments:
            if segment.is_speech:
                start_sample = int(segment.start_time * self.sample_rate)
                end_sample = int(segment.end_time * self.sample_rate)
                speech_segments.append(audio[start_sample:end_sample])

        if speech_segments:
            return np.concatenate(speech_segments)
        else:
            # 음성이 검출되지 않으면 전체 오디오 반환
            return audio

    def _calculate_quality_scores(
        self, original_audio: np.ndarray, enhanced_audio: np.ndarray, segments: list[AudioSegment]
    ) -> AudioQualityScore:
        """오디오 품질 점수 계산"""

        # 명확도 점수 (고주파 성분 강도)
        min_len = min(len(original_audio), len(enhanced_audio))
        if min_len == 0:
            clarity_score = 0.0
        else:
            original_fft = np.fft.fft(original_audio[:min_len])
            enhanced_fft = np.fft.fft(enhanced_audio[:min_len])
            high_freq_mask = np.abs(np.fft.fftfreq(min_len)) >= 0.25
            if np.any(high_freq_mask):
                clarity_score = min(
                    float(
                        np.mean(
                            np.abs(enhanced_fft[high_freq_mask])
                            / (np.abs(original_fft[high_freq_mask]) + 1e-8)
                        )
                    ),
                    1.0,
                )
            else:
                clarity_score = 0.0

        # 노이즈 레벨 (정적/배경음 비율)
        silent_frames = sum(1 for s in segments if not s.is_speech)
        noise_level = silent_frames / len(segments) if segments else 0.0

        # 볼륨 레벨 (RMS 기준)
        if len(original_audio) == 0 or len(enhanced_audio) == 0:
            volume_level = 0.0
        else:
            original_rms = np.sqrt(np.mean(original_audio**2))
            enhanced_rms = np.sqrt(np.mean(enhanced_audio**2))
            volume_level = min(float(enhanced_rms / (original_rms + 1e-8)), 1.0)

        # 음성 활동 비율
        speech_ratio = sum(1 for s in segments if s.is_speech) / len(segments) if segments else 0.0

        # 전체 점수 (가중 평균)
        overall_score = (
            clarity_score * 0.4 + (1 - noise_level) * 0.3 + volume_level * 0.2 + speech_ratio * 0.1
        )

        clarity_score = float(np.nan_to_num(clarity_score, nan=0.0, posinf=1.0, neginf=0.0))
        overall_score = float(np.nan_to_num(overall_score, nan=0.0, posinf=1.0, neginf=0.0))

        return AudioQualityScore(
            overall_score=round(overall_score, 3),
            clarity_score=round(clarity_score, 3),
            noise_level=round(noise_level, 3),
            volume_level=round(volume_level, 3),
            voice_activity_ratio=round(speech_ratio, 3),
        )

    async def enhance_audio(
        self, file_path: Path, request: AudioEnhancementRequest
    ) -> EnhancementResult:
        """오디오 향상 처리"""

        # 1. 오디오 파일 읽기
        original_audio, sr = self._read_audio_file(file_path)

        # 2. 음성 활동 검출
        segments = self._detect_voice_activity(original_audio)

        # 3. 기본 전처리
        processed_audio = original_audio.copy()

        # 4. 노이즈 제거 적용
        if request.enhancement_mode != EnhancementMode.MUSIC_FOCUSED:
            processed_audio = self._apply_noise_reduction(
                processed_audio, request.noise_reduction_level
            )

        # 5. 보이스 향상 적용
        if request.enhancement_mode != EnhancementMode.CLEAN:
            processed_audio = self._voice_enhancement(processed_audio, request.voice_enhancement)

        # 6. 음성만 추출
        if request.extract_speech_only:
            processed_audio = self._extract_speech_segments(processed_audio, segments)

        # 7. 오디오 정규화
        if request.normalize_audio:
            processed_audio = self._normalize_audio(processed_audio)

        # 8. 샘플 레이트 변환 (필요 시)
        if request.target_sample_rate and sr != request.target_sample_rate:
            processed_audio = self._resample_audio(processed_audio, sr, request.target_sample_rate)
            sr = request.target_sample_rate

        # 9. 품질 점수 계산
        quality_scores = self._calculate_quality_scores(original_audio, processed_audio, segments)

        # 10. 저장 경로 생성
        output_dir = Path(tempfile.mkdtemp(prefix="enhanced_audio_"))
        output_file = output_dir / f"enhanced_{file_path.name}"

        # 11. 향상된 오디오 저장
        sf.write(output_file, processed_audio, sr)

        # 12. 통계 정보 생성
        original_size = file_path.stat().st_size
        enhanced_size = output_file.stat().st_size
        compression_ratio = original_size / enhanced_size if enhanced_size > 0 else 1.0

        # 13. 생성 세그먼트 정보 (JSON 직렬화 가능 형식)
        segment_data = [
            {
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "is_speech": seg.is_speech,
                "confidence": round(seg.confidence, 3),
                "rms_level": round(seg.rms_level, 6),
            }
            for seg in segments
        ]

        # 14. 경고 메시지 생성
        warnings = []
        if quality_scores.overall_score < 0.5:
            warnings.append("오디오 품질이 낮습니다. 원본 오디오 품질을 확인해 주세요.")
        if request.extract_speech_only and len(segment_data) < 5:
            warnings.append("음성이 매우 적게 검출되었습니다.")
        if enhanced_size > original_size * 2:
            warnings.append("처리 후 파일 크기가 크게 증가했습니다.")

        return EnhancementResult(
            enhanced_task_id=str(uuid.uuid4()),
            original_file_size=original_size,
            enhanced_file_size=enhanced_size,
            processing_time_seconds=0.0,  # 실제 처리 시간은 외부에서 계산
            compression_ratio=round(compression_ratio, 3),
            quality_scores=quality_scores,
            segments=segment_data,
            warnings=warnings,
            metadata={
                "original_sample_rate": sr,
                "target_sample_rate": request.target_sample_rate,
                "enhancement_mode": request.enhancement_mode.value,
                "noise_reduction_level": request.noise_reduction_level.value,
                "voice_enhancement": request.voice_enhancement.value,
                "extract_speech_only": request.extract_speech_only,
            },
        )
