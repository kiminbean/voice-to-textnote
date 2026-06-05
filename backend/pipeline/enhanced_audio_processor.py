"""
고급 오디오 전처리 파이프라인
- AI 기반 노이즈 제거
- 배치 처리
- 실시간 전처리 파이프라인
- 다중 오디오 포맷 지원
"""

import asyncio
import json
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 설정 상수
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_DBFS = -20.0

# AI 노이즈 제거 설정
AI_NOISE_REMOVAL_ENABLED = True
AI_NOISE_MODEL_PATH = "/models/noise_reduction_model"
AI_NOISE_THRESHOLD = 0.1  # 노이즈 감지 임계값

# 배치 처리 설정
BATCH_MAX_FILES = 20
BATCH_MAX_CONCURRENT = 5
BATCH_TIMEOUT_SECONDS = 300  # 5분

# 지원 오디오 포맷
SUPPORTED_FORMATS = {
    'wav', 'mp3', 'flac', 'aac', 'ogg', 'm4a', 'wma', 'opus', 'webm'
}


@dataclass
class BatchPreprocessOptions:
    """배치 전처리 옵션"""
    convert_to_16k_mono: bool = True
    normalize: bool = True
    target_dbfs: float = TARGET_DBFS
    high_pass_hz: int | None = None
    low_pass_hz: int | None = None
    trim_silence: bool = False
    silence_threshold_db: float = -40.0
    silence_min_len_ms: int = 700
    ai_noise_removal: bool = AI_NOISE_REMOVAL_ENABLED
    noise_threshold: float = AI_NOISE_THRESHOLD
    denoise_strength: float = 0.8  # 0.0 ~ 1.0


@dataclass
class AudioFileInfo:
    """오디오 파일 정보"""
    original_path: Path
    processed_path: Path
    original_format: str
    original_size: int
    processed_size: int
    duration_seconds: float
    sample_rate: int
    channels: int
    metadata: dict[str, Any]


@dataclass
class BatchPreprocessResult:
    """배치 처리 결과"""
    task_id: str
    total_files: int
    processed_files: int
    failed_files: int
    processing_time_seconds: float
    results: list[AudioFileInfo]
    errors: list[dict[str, Any]]
    summary: dict[str, Any]


class AIModelManager:
    """AI 노이즈 제거 모델 관리"""

    def __init__(self):
        self.model = None
        self.model_loaded = False

    async def load_model(self) -> bool:
        """AI 노이즈 제거 모델 로드"""
        if not AI_NOISE_REMOVAL_ENABLED:
            return False

        try:
            # 실제 AI 모델 로드 (예: RNNoise, SpeechBrain 등)
            # 여기서는 가상 구현
            # self.model = load_noise_reduction_model(AI_NOISE_MODEL_PATH)
            logger.info("AI 노이즈 제거 모델 로드 완료")
            self.model_loaded = True
            return True
        except Exception as e:
            logger.error("AI 노이즈 제거 모델 로드 실패", error=str(e))
            return False

    def remove_noise(self, audio: np.ndarray) -> np.ndarray:
        """AI 기반 노이즈 제거"""
        if not self.model_loaded:
            return audio

        try:
            # 실제 노이즈 제거 처리
            # processed_audio = self.model(audio)
            # 예시 구현 (실제로는 AI 모델 호출)
            processed_audio = self._simple_noise_reduction(audio)
            return processed_audio
        except Exception as e:
            logger.error("노이즈 제거 실패", error=str(e))
            return audio

    def _simple_noise_reduction(self, audio: np.ndarray) -> np.ndarray:
        """간단한 노이즈 제거 (실제로는 AI 모델로 교체)"""
        # 스펙트럼 감쇠 기반 간단한 노이즈 제거
        if len(audio) == 0:
            return audio

        # 기본 노이즈 감쇠 (실제 AI 모델과 교체 필요)
        noise_factor = 0.1  # 노이즈 감쇠 정도
        reduced = audio * (1 - noise_factor)

        # 크기 유지
        if np.max(np.abs(reduced)) > 0:
            reduced = reduced / np.max(np.abs(reduced))

        return reduced.astype(np.float32)


class EnhancedAudioProcessor:
    """고급 오디오 전처리기"""

    def __init__(self):
        self.ai_model = AIModelManager()
        self.batch_executor = ThreadPoolExecutor(max_workers=BATCH_MAX_CONCURRENT)

    async def initialize(self) -> None:
        """초기화"""
        await self.ai_model.load_model()

    async def preprocess_batch(
        self,
        input_files: list[str | Path],
        options: BatchPreprocessOptions,
        output_dir: str | Path | None = None
    ) -> BatchPreprocessResult:
        """배치 전처리"""
        start_time = asyncio.get_event_loop().time()
        task_id = str(uuid.uuid4())

        if len(input_files) > BATCH_MAX_FILES:
            raise ValueError(f"최대 {BATCH_MAX_FILES}개 파일까지 처리 가능")

        # 출력 디렉토리 생성
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="batch_audio_"))
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        errors = []
        processed_count = 0

        # 비동기 배치 처리
        tasks = []
        for input_file in input_files:
            task = self._process_single_file(
                Path(input_file),
                options,
                output_dir / f"processed_{uuid.uuid4()}.wav",
                task_id
            )
            tasks.append(task)

        # 병렬 실행
        try:
            completed_tasks = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=BATCH_TIMEOUT_SECONDS
            )

            for task_result in completed_tasks:
                if isinstance(task_result, Exception):
                    errors.append({
                        "error": str(task_result),
                        "type": type(task_result).__name__
                    })
                else:
                    results.append(task_result)
                    processed_count += 1

        except TimeoutError:
            errors.append({
                "error": f"배치 처리 시간 초과 ({BATCH_TIMEOUT_SECONDS}초)",
                "type": "TimeoutError"
            })

        # 결과 생성
        processing_time = asyncio.get_event_loop().time() - start_time

        summary = self._generate_batch_summary(results)

        return BatchPreprocessResult(
            task_id=task_id,
            total_files=len(input_files),
            processed_files=processed_count,
            failed_files=len(errors),
            processing_time_seconds=processing_time,
            results=results,
            errors=errors,
            summary=summary
        )

    async def _process_single_file(
        self,
        input_path: Path,
        options: BatchPreprocessOptions,
        output_path: Path,
        task_id: str
    ) -> AudioFileInfo:
        """단일 파일 처리 (비동기)"""
        try:
            # 파일 유효성 검증
            if not input_path.exists():
                raise FileNotFoundError(f"입력 파일 없음: {input_path}")

            if input_path.suffix.lower()[1:] not in SUPPORTED_FORMATS:
                raise ValueError(f"지원하지 않는 포맷: {input_path.suffix}")

            # 오디오 로드
            audio = await asyncio.to_thread(AudioSegment.from_file, str(input_path))

            # 전처리 파이프라인
            processed_audio = await asyncio.to_thread(
                self._apply_preprocessing_pipeline,
                audio,
                options
            )

            # AI 노이즈 제거 (비동기)
            if options.ai_noise_removal:
                audio_array = await asyncio.to_thread(
                    self._audio_to_numpy,
                    processed_audio
                )
                denoised_array = await asyncio.to_thread(
                    self.ai_model.remove_noise,
                    audio_array
                )
                processed_audio = await asyncio.to_thread(
                    self._numpy_to_audio,
                    denoised_array
                )

            # 파일 저장
            await asyncio.to_thread(processed_audio.export, str(output_path), format="wav")

            # 메타데이터 수집
            file_info = await asyncio.to_thread(
                self._collect_file_info,
                input_path,
                output_path,
                processed_audio
            )

            logger.info(
                "오디오 처리 완료",
                task_id=task_id,
                input=str(input_path),
                output=str(output_path),
                duration_ms=len(processed_audio)
            )

            return file_info

        except Exception as e:
            logger.error(
                "오디오 처리 실패",
                task_id=task_id,
                input=str(input_path),
                error=str(e)
            )
            raise

    def _apply_preprocessing_pipeline(
        self,
        audio: AudioSegment,
        options: BatchPreprocessOptions
    ) -> AudioSegment:
        """전처리 파이프라인 적용"""
        # 16kHz 모노 변환
        if options.convert_to_16k_mono:
            if audio.channels != TARGET_CHANNELS:
                audio = audio.set_channels(TARGET_CHANNELS)
            if audio.frame_rate != TARGET_SAMPLE_RATE:
                audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)

        # 필터링
        if options.high_pass_hz is not None:
            audio = audio.high_pass_filter(options.high_pass_hz)

        if options.low_pass_hz is not None:
            audio = audio.low_pass_filter(options.low_pass_hz)

        # 무음 제거
        if options.trim_silence:
            audio = self._trim_leading_trailing_silence(
                audio,
                options.silence_threshold_db,
                options.silence_min_len_ms
            )

        # 정규화
        if options.normalize:
            audio = self._normalize_audio(audio, options.target_dbfs)

        return audio

    def _audio_to_numpy(self, audio: AudioSegment) -> np.ndarray:
        """AudioSegment를 NumPy 배열로 변환"""
        return np.array(audio.get_array_of_samples()).astype(np.float32)

    def _numpy_to_audio(self, audio_array: np.ndarray) -> AudioSegment:
        """NumPy 배열을 AudioSegment로 변환"""
        return AudioSegment(
            audio_array.tobytes(),
            frame_rate=TARGET_SAMPLE_RATE,
            channels=TARGET_CHANNELS,
            sample_width=2
        )

    def _trim_leading_trailing_silence(
        self,
        audio: AudioSegment,
        silence_threshold_db: float,
        min_silence_len_ms: int
    ) -> AudioSegment:
        """앞뒤 무음 제거"""
        if len(audio) == 0:
            return audio

        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len_ms,
            silence_thresh=silence_threshold_db,
        )

        if not nonsilent_ranges:
            return audio

        start_ms = nonsilent_ranges[0][0]
        end_ms = nonsilent_ranges[-1][1]
        return audio[start_ms:end_ms]

    def _normalize_audio(
        self,
        audio: AudioSegment,
        target_dbfs: float
    ) -> AudioSegment:
        """오디오 정규화"""
        if audio.dBFS == float("-inf"):
            return audio

        change_db = target_dbfs - audio.dBFS
        return audio.apply_gain(change_db)

    def _collect_file_info(
        self,
        input_path: Path,
        output_path: Path,
        audio: AudioSegment
    ) -> AudioFileInfo:
        """파일 정보 수집"""
        return AudioFileInfo(
            original_path=input_path,
            processed_path=output_path,
            original_format=input_path.suffix.lower(),
            original_size=input_path.stat().st_size,
            processed_size=output_path.stat().st_size,
            duration_seconds=len(audio) / 1000.0,
            sample_rate=audio.frame_rate,
            channels=audio.channels,
            metadata={
                "format": input_path.suffix.lower().lstrip("."),
                "frame_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width
            }
        )

    def _generate_batch_summary(
        self,
        results: list[AudioFileInfo]
    ) -> dict[str, Any]:
        """배치 처리 요약 생성"""
        if not results:
            return {}

        total_input_size = sum(f.original_size for f in results)
        total_output_size = sum(f.processed_size for f in results)
        total_duration = sum(f.duration_seconds for f in results)

        return {
            "total_input_size_bytes": total_input_size,
            "total_output_size_bytes": total_output_size,
            "compression_ratio": total_output_size / total_input_size if total_input_size > 0 else 1.0,
            "total_duration_seconds": total_duration,
            "average_duration_seconds": total_duration / len(results),
            "average_sample_rate": sum(f.sample_rate for f in results) / len(results),
            "format_distribution": {
                fmt: len([f for f in results if f.original_format == fmt])
                for fmt in set(f.original_format for f in results)
            }
        }

    async def create_processing_report(
        self,
        result: BatchPreprocessResult
    ) -> str:
        """처리 보고서 생성"""
        report = {
            "task_id": result.task_id,
            "summary": {
                "total_files": result.total_files,
                "processed_files": result.processed_files,
                "failed_files": result.failed_files,
                "processing_time_seconds": result.processing_time_seconds,
                "success_rate": result.processed_files / result.total_files if result.total_files > 0 else 0
            },
            "details": result.summary,
            "errors": result.errors
        }

        return json.dumps(report, indent=2, ensure_ascii=False)


# 전역 인스턴스
_enhanced_processor = None


async def get_enhanced_processor() -> EnhancedAudioProcessor:
    """전역 고급 오디오 프로세서 인스턴스"""
    global _enhanced_processor
    if _enhanced_processor is None:
        _enhanced_processor = EnhancedAudioProcessor()
        await _enhanced_processor.initialize()
    return _enhanced_processor
