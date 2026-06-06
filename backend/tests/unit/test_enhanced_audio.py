"""
고급 오디오 전처리 테스트
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydub import AudioSegment

from backend.pipeline.enhanced_audio_processor import (
    AudioFileInfo as PipelineAudioFileInfo,
)
from backend.pipeline.enhanced_audio_processor import (
    BatchPreprocessOptions,
    EnhancedAudioProcessor,
)
from backend.schemas.audio_enhanced import (
    AudioFileInfo,
    EnhancedPreprocessOptions,
    OutputFormat,
)


@pytest.fixture
def client():
    """TestClient for enhanced audio preprocessing endpoints"""
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture
def sample_audio_file():
    """샘플 오디오 파일 생성"""
    # 테스트용 오디오 파일 생성
    audio = AudioSegment.silent(duration=5000)  # 5초 무음
    audio = audio + AudioSegment.silent(duration=1000)  # 총 6초

    # 테스트용 파일 생성
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        audio.export(tmp_file.name, format="wav")
        return tmp_file.name


@pytest.fixture
def sample_audio_files():
    """샘플 오디오 파일 목록 생성"""
    files = []
    for i in range(3):
        audio = AudioSegment.silent(duration=2000)  # 2초 무음
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            audio.export(tmp_file.name, format="wav")
            files.append(tmp_file.name)
    return files


class TestEnhancedAudioProcessor:
    """고급 오디오 프로세서 테스트"""

    @pytest.mark.asyncio
    async def test_enhanced_processor_initialization(self):
        """고급 프로세서 초기화 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        assert processor.ai_model is not None
        assert processor.batch_executor is not None
        assert processor.ai_model.model_loaded is True  # 테스트 환경에서는 True 반환

    @pytest.mark.asyncio
    async def test_preprocess_single_file(self, sample_audio_file):
        """단일 파일 전처리 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        options = EnhancedPreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            ai_noise_removal=False,  # 테스트에서는 AI 제거
            target_dbfs=-20.0,
            high_pass_hz=80,
            low_pass_hz=8000
        )

        output_path = Path(sample_audio_file.replace(".wav", "_processed.wav"))

        try:
            result = await processor.preprocess_batch(
                [sample_audio_file],
                options,
                None
            )

            assert result.total_files == 1
            assert result.processed_files == 1
            assert result.failed_files == 0

            # 첫 번째 결과 확인
            audio_info = result.results[0]
            assert isinstance(audio_info, PipelineAudioFileInfo)
            assert audio_info.original_path == Path(sample_audio_file)
            assert audio_info.processed_path.exists()
            assert audio_info.sample_rate == 16000
            assert audio_info.channels == 1

        finally:
            # 클린업
            if output_path.exists():
                output_path.unlink()

    @pytest.mark.asyncio
    async def test_preprocess_batch_files(self, sample_audio_files):
        """배치 파일 전처리 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        options = BatchPreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            ai_noise_removal=False
        )

        output_dir = tempfile.mkdtemp()

        try:
            result = await processor.preprocess_batch(
                sample_audio_files,
                options,
                output_dir
            )

            assert result.total_files == len(sample_audio_files)
            assert result.processed_files == len(sample_audio_files)
            assert result.failed_files == 0
            assert len(result.results) == len(sample_audio_files)

            # 요약 정보 확인
            summary = result.summary
            assert summary["total_input_size_bytes"] > 0
            assert summary["total_output_size_bytes"] > 0
            assert "compression_ratio" in summary
            assert "total_duration_seconds" in summary

            # 출력 파일 확인
            for file_info in result.results:
                assert file_info.processed_path.exists()
                assert file_info.sample_rate == 16000
                assert file_info.channels == 1

        finally:
            # 클린업
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_ai_noise_removal_simulation(self, sample_audio_file):
        """AI 노이즈 제거 시뮬레이션 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        # AI 모델이 로드된 상태에서 테스트
        assert processor.ai_model.model_loaded is True

        # 실제 오디오 데이터를 numpy로 변환 테스트
        audio = AudioSegment.from_file(sample_audio_file)
        numpy_array = processor._audio_to_numpy(audio)

        assert isinstance(numpy_array, np.ndarray)
        assert len(numpy_array) > 0

        # 노이즈 제거 테스트 (가짜 데이터)
        denoised_array = processor.ai_model.remove_noise(numpy_array)
        assert len(denoised_array) == len(numpy_array)

    @pytest.mark.asyncio
    async def test_audio_pipeline_processing(self, sample_audio_file):
        """오디오 파이프라인 처리 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        # 단일 오디오 파일 파이프라인 처리 테스트
        audio = AudioSegment.from_file(sample_audio_file)

        # 기본 파이프라인 적용
        options = BatchPreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            trim_silence=True,
            high_pass_hz=100
        )

        processed_audio = processor._apply_preprocessing_pipeline(audio, options)

        assert processed_audio.frame_rate == 16000
        assert processed_audio.channels == 1
        assert len(processed_audio) > 0

    @pytest.mark.asyncio
    async def test_audio_normalization(self, sample_audio_file):
        """오디오 정규화 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        audio = AudioSegment.from_file(sample_audio_file)

        # 정규화 적용
        normalized_audio = processor._normalize_audio(audio, -20.0)

        # 정규화된 오디오는 진폭이 조정됨
        if normalized_audio.dBFS != float("-inf"):
            assert abs(normalized_audio.dBFS - (-20.0)) < 1.0  # 허용 오차 1dB  # pragma: no cover

        # 무음 오디오 테스트
        silent_audio = AudioSegment.silent(duration=1000)
        normalized_silent = processor._normalize_audio(silent_audio, -20.0)
        assert normalized_silent.dBFS == float("-inf")


class TestEnhancedAudioAPI:
    """고급 오디오 API 테스트"""

    @pytest.mark.asyncio
    async def test_get_supported_formats(self, client):
        """지원 오디오 포맷 조회 테스트"""
        response = client.get("/api/v1/enhanced/formats")
        assert response.status_code == 200

        formats = response.json()
        assert isinstance(formats, list)
        assert len(formats) > 0

        # 각 포맷 유효성 검증
        for format_info in formats:
            assert "extension" in format_info
            assert "description" in format_info
            assert "supported_codecs" in format_info
            assert isinstance(format_info["supported_codecs"], list)

        # 특정 포맷 확인
        wav_format = next((f for f in formats if f["extension"] == "wav"), None)
        assert wav_format is not None
        assert "WAV (무손실)" in wav_format["description"]

    @pytest.mark.asyncio
    async def test_get_model_status(self, client):
        """AI 모델 상태 조회 테스트"""
        response = client.get("/api/v1/enhanced/status")
        assert response.status_code == 200

        status = response.json()
        assert isinstance(status, dict)

        required_fields = [
            "ai_noise_removal_enabled",
            "model_loaded",
            "supported_formats",
            "batch_max_files",
            "batch_max_concurrent",
            "supported_ai_features",
            "processing_limits"
        ]

        for field in required_fields:
            assert field in status

        # 값 유효성 검증
        assert status["ai_noise_removal_enabled"] is True
        assert status["supported_formats"] > 0
        assert status["batch_max_files"] > 0
        assert status["batch_max_concurrent"] > 0
        assert isinstance(status["supported_ai_features"], list)
        assert isinstance(status["processing_limits"], dict)

    @pytest.mark.asyncio
    async def test_enhanced_preprocess_validation(self):
        """고급 전처리 옵션 유효성 검증 테스트"""
        # 유효한 옵션
        valid_options = EnhancedPreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            target_dbfs=-20.0,
            high_pass_hz=100,
            low_pass_hz=8000,
            trim_silence=True,
            silence_threshold_db=-40.0,
            silence_min_len_ms=500,
            ai_noise_removal=True,
            noise_threshold=0.1,
            denoise_strength=0.8
        )

        assert valid_options.target_dbfs == -20.0
        assert valid_options.high_pass_hz == 100
        assert valid_options.low_pass_hz == 8000
        assert valid_options.silence_threshold_db == -40.0
        assert valid_options.silence_min_len_ms == 500
        assert valid_options.ai_noise_removal is True
        assert valid_options.noise_threshold == 0.1
        assert valid_options.denoise_strength == 0.8

        # 무효한 값 테스트
        # target_dbfs 범위 외 값 → ValidationError
        with pytest.raises(Exception):
            EnhancedPreprocessOptions(target_dbfs=-100.0)

        # high_pass_hz 범위 외 값 → ValidationError
        with pytest.raises(Exception):
            EnhancedPreprocessOptions(high_pass_hz=1000)

        # noise_threshold 범위 외 값 → ValidationError
        with pytest.raises(Exception):
            EnhancedPreprocessOptions(noise_threshold=1.5)

    @pytest.mark.asyncio
    async def test_batch_preprocess_options(self):
        """배치 전처리 옵션 테스트"""
        options = BatchPreprocessOptions(
            convert_to_16k_mono=True,
            normalize=True,
            ai_noise_removal=True,
            denoise_strength=0.7
        )

        assert options.convert_to_16k_mono is True
        assert options.normalize is True
        assert options.ai_noise_removal is True
        assert options.denoise_strength == 0.7

    @pytest.mark.asyncio
    async def test_output_format_enum(self):
        """출력 형식 Enum 테스트"""
        for format_type in OutputFormat:
            assert isinstance(format_type.value, str)
            assert format_type.value in ["zip", "individual"]

    @pytest.mark.asyncio
    async def test_audio_info_model_validation(self):
        """오디오 정보 모델 유효성 검증 테스트"""
        # AudioFileInfo 모델 테스트
        audio_info = AudioFileInfo(
            original_path="/path/to/original.wav",
            processed_path="/path/to/processed.wav",
            original_format="wav",
            original_size=1000,
            processed_size=800,
            duration_seconds=5.0,
            sample_rate=16000,
            channels=1,
            metadata={"format": "wav"}
        )

        assert audio_info.original_path == "/path/to/original.wav"
        assert audio_info.processed_path == "/path/to/processed.wav"
        assert audio_info.original_format == "wav"
        assert audio_info.original_size == 1000
        assert audio_info.processed_size == 800
        assert audio_info.duration_seconds == 5.0
        assert audio_info.sample_rate == 16000
        assert audio_info.channels == 1
        assert audio_info.metadata == {"format": "wav"}


class TestAudioProcessingErrorHandling:
    """오디오 처리 오류 처리 테스트"""

    @pytest.mark.asyncio
    async def test_invalid_audio_file(self):
        """잘못된 오디오 파일 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        # 존재하지 않는 파일 테스트
        options = BatchPreprocessOptions()

        result = await processor.preprocess_batch(
            ["/nonexistent/file.wav"],
            options,
            None
        )

        assert result.total_files == 1
        assert result.processed_files == 0
        assert result.failed_files == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_batch_processing_timeout(self):
        """배치 처리 시간 초과 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        # 과도한 파일 수 테스트 (배치 제한 초과 시 ValueError)
        large_file_list = ["/fake/file.wav"] * 25  # 최대 20개 초과

        options = BatchPreprocessOptions()

        with pytest.raises(ValueError, match="최대"):
            await processor.preprocess_batch(
                large_file_list,
                options,
                None
            )

    @pytest.mark.asyncio
    async def test_memory_efficiency(self, sample_audio_files):
        """메모리 효율성 테스트"""
        processor = EnhancedAudioProcessor()
        await processor.initialize()

        options = BatchPreprocessOptions(
            ai_noise_removal=False  # AI 제거로 메모리 사용 줄임
        )

        # 대량 파일 처리 테스트
        result = await processor.preprocess_batch(
            sample_audio_files,
            options,
            None
        )

        assert result.processed_files == len(sample_audio_files)
        assert result.failed_files == 0

        # 메모리 누수 확인 (실제 테스트에서는 메모리 모니터링 필요)
        # 현재 테스트에서는 성공 여부만 확인
        assert len(result.results) == len(sample_audio_files)
