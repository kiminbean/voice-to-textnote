"""
고급 오디오 전처리 API
- AI 기반 노이즈 제거
- 배치 처리
- 실시간 전처리 파이프라인
- 다중 오디오 포맷 지원

엔드포인트:
- POST /api/v1/audio/enhanced/preprocess - 단일 고급 전처리
- POST /api/v1/audio/enhanced/batch - 배치 전처리
- GET /api/v1/audio/enhanced/formats - 지원 오디오 포맷 조회
- GET /api/v1/audio/enhanced/status - AI 모델 상태 조회
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.app.errors import (
    bad_request,
    internal_server_error,
    service_unavailable,
)
from backend.pipeline.enhanced_audio_processor import (
    BatchPreprocessOptions,
    get_enhanced_processor,
)
from backend.schemas.audio_enhanced import (
    AudioFileInfo as AudioFileInfoSchema,
)
from backend.schemas.audio_enhanced import (
    BatchPreprocessResponse,
    BatchSummary,
    EnhancedPreprocessOptions,
    FormatInfo,
    ModelStatusResponse,
    PreprocessResponse,
)
from backend.utils.logger import get_logger
from backend.utils.validators import validate_audio_format

logger = get_logger(__name__)

router = APIRouter(prefix="/enhanced", tags=["enhanced-audio-preprocess"])


# -----------------------------------------------------------------
# 단일 파일 고급 전처리 엔드포인트
# -----------------------------------------------------------------


@router.post(
    "/preprocess",
    response_model=PreprocessResponse,
    responses={
        200: {"description": "처리된 WAV 파일 (audio/wav)"},
        400: {"description": "잘못된 파일 또는 손상된 오디오"},
        413: {"description": "파일 크기 초과"},
        422: {"description": "전처리 옵션 검증 실패"},
        503: {"description": "전처리 비활성화 상태"},
    },
)
async def enhanced_preprocess_endpoint(
    file: UploadFile = File(..., description="원본 오디오 파일"),
    convert_to_16k_mono: bool = Form(default=True),
    normalize: bool = Form(default=True),
    target_dbfs: float = Form(default=-20.0),
    high_pass_hz: int | None = Form(default=None),
    low_pass_hz: int | None = Form(default=None),
    trim_silence: bool = Form(default=False),
    silence_threshold_db: float = Form(default=-40.0),
    silence_min_len_ms: int = Form(default=700),
    ai_noise_removal: bool = Form(default=True),
    noise_threshold: float = Form(default=0.1),
    denoise_strength: float = Form(default=0.8),
) -> FileResponse:
    """단일 파일 고급 전처리 (AI 노이즈 제거 포함)"""
    if not settings.audio_preprocess_enabled:
        service_unavailable("오디오 전처리 기능이 비활성화되어 있습니다.")

    # 파일 유효성 검증
    filename = file.filename or "audio"
    is_valid, msg = validate_audio_format(filename)
    if not is_valid:
        bad_request(msg)

    # 옵션 구성
    options = EnhancedPreprocessOptions(
        convert_to_16k_mono=convert_to_16k_mono,
        normalize=normalize,
        target_dbfs=target_dbfs,
        high_pass_hz=high_pass_hz,
        low_pass_hz=low_pass_hz,
        trim_silence=trim_silence,
        silence_threshold_db=silence_threshold_db,
        silence_min_len_ms=silence_min_len_ms,
        ai_noise_removal=ai_noise_removal,
        noise_threshold=noise_threshold,
        denoise_strength=denoise_strength,
    )

    try:
        # 고급 프로세서 가져오기
        processor = await get_enhanced_processor()

        # 임시 파일 생성
        max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
        suffix = Path(filename).suffix or ".bin"
        src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="enhanced_in_")
        src_path = Path(src_name)

        # 파일 저장
        bytes_read = 0
        try:
            with open(src_fd, "wb") as fp:
                while chunk := await file.read(1024 * 1024):
                    bytes_read += len(chunk)
                    if bytes_read > max_bytes:
                        bad_request(
                            f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                        )
                    fp.write(chunk)
        except Exception as exc:
            src_path.unlink(missing_ok=True)
            logger.error("업로드 저장 실패", error=str(exc))
            bad_request(f"업로드 처리 실패: {exc}")

        # 처리 수행 (비동기)
        try:
            batch_options = BatchPreprocessOptions(**options.model_dump())
            result = await processor.preprocess_batch([src_path], batch_options, None)

            if result.failed_files > 0:
                raise HTTPException(status_code=400, detail="오디오 처리 실패")

            processed_file = result.results[0]
            processed_path = processed_file.processed_path

            # 메타데이터 헤더
            metadata = {
                "original_filename": filename,
                "original_size_bytes": processed_file.original_size,
                "processed_size_bytes": processed_file.processed_size,
                "duration_seconds": processed_file.duration_seconds,
                "sample_rate": processed_file.sample_rate,
                "channels": processed_file.channels,
                "applied_options": options.model_dump(),
                "ai_noise_removed": processed_file.metadata.get("ai_noise_removed", False),
            }

            # 클린업 태스크
            def cleanup():
                src_path.unlink(missing_ok=True)
                processed_path.unlink(missing_ok=True)

            output_name = f"{Path(filename).stem}_enhanced.wav"
            return FileResponse(
                path=processed_path,
                media_type="audio/wav",
                filename=output_name,
                background=BackgroundTask(cleanup),
                headers={"X-Enhanced-Preprocess-Meta": str(metadata)},
            )

        except Exception as exc:
            src_path.unlink(missing_ok=True)
            logger.error("오디오 전처리 실패", error=str(exc))
            raise HTTPException(status_code=400, detail=f"오디오 전처리 실패: {exc}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("고급 전처리 API 오류", error=str(exc))
        internal_server_error("고급 전처리 중 오류가 발생했습니다")


# -----------------------------------------------------------------
# 배치 전처리 엔드포인트
# -----------------------------------------------------------------


@router.post(
    "/batch",
    response_model=BatchPreprocessResponse,
    responses={
        200: {"description": "배치 처리 결과"},
        400: {"description": "잘못된 요청"},
        413: {"description": "파일 크기 초과"},
        422: {"description": "옵션 검증 실패"},
        503: {"description": "전처리 비활성화 상태"},
    },
)
async def batch_preprocess_endpoint(
    files: list[UploadFile] = File(..., description="배치 처리할 오디오 파일들"),
    convert_to_16k_mono: bool = Form(default=True),
    normalize: bool = Form(default=True),
    target_dbfs: float = Form(default=-20.0),
    high_pass_hz: int | None = Form(default=None),
    low_pass_hz: int | None = Form(default=None),
    trim_silence: bool = Form(default=False),
    silence_threshold_db: float = Form(default=-40.0),
    silence_min_len_ms: int = Form(default=700),
    ai_noise_removal: bool = Form(default=True),
    noise_threshold: float = Form(default=0.1),
    denoise_strength: float = Form(default=0.8),
    output_format: str = Form(default="zip", description="출력 형식: zip, individual"),
    return_report: bool = Form(default=True, description="상세 보고서 포함"),
) -> BatchPreprocessResponse:
    """배치 오디오 전처리"""
    if not settings.audio_preprocess_enabled:
        service_unavailable("오디오 전처리 기능이 비활성화되어 있습니다.")

    if len(files) > 20:
        bad_request("최대 20개 파일까지 처리 가능합니다")

    # 파일 유효성 검증
    validated_files = []
    for file in files:
        filename = file.filename or "audio"
        is_valid, msg = validate_audio_format(filename)
        if not is_valid:
            bad_request(f"{filename}: {msg}")
        validated_files.append(file)

    # 옵션 구성
    options = BatchPreprocessOptions(
        convert_to_16k_mono=convert_to_16k_mono,
        normalize=normalize,
        target_dbfs=target_dbfs,
        high_pass_hz=high_pass_hz,
        low_pass_hz=low_pass_hz,
        trim_silence=trim_silence,
        silence_threshold_db=silence_threshold_db,
        silence_min_len_ms=silence_min_len_ms,
        ai_noise_removal=ai_noise_removal,
        noise_threshold=noise_threshold,
        denoise_strength=denoise_strength,
    )

    try:
        # 고급 프로세서 가져오기
        processor = await get_enhanced_processor()

        # 임시 파일 저장
        temp_files: list[Path] = []
        try:
            for file in validated_files:
                max_bytes = settings.audio_preprocess_max_file_mb * 1024 * 1024
                suffix = Path(file.filename or "audio").suffix or ".bin"
                src_fd, src_name = tempfile.mkstemp(suffix=suffix, prefix="batch_in_")
                src_path = Path(src_name)
                temp_files.append(src_path)

                # 파일 저장
                bytes_read = 0
                with open(src_fd, "wb") as fp:
                    while chunk := await file.read(1024 * 1024):
                        bytes_read += len(chunk)
                        if bytes_read > max_bytes:
                            bad_request(
                                f"파일 크기가 {settings.audio_preprocess_max_file_mb}MB를 초과합니다."
                            )
                        fp.write(chunk)

            # 배치 처리 수행
            result = await processor.preprocess_batch(list(temp_files), options, None)

            # 보고서 생성
            report = await processor.create_processing_report(result) if return_report else None

            return BatchPreprocessResponse(
                task_id=result.task_id,
                total_files=result.total_files,
                processed_files=result.processed_files,
                failed_files=result.failed_files,
                processing_time_seconds=result.processing_time_seconds,
                summary=BatchSummary.model_validate(result.summary),
                results=[
                    AudioFileInfoSchema.model_validate(item)
                    for item in result.results
                ],
                errors=result.errors,
                report=report,
            )

        except Exception as exc:
            logger.error("배치 처리 실패", error=str(exc))
            raise HTTPException(status_code=400, detail=f"배치 처리 실패: {exc}")

        finally:
            # 클린업
            for temp_file in temp_files:
                temp_file.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("배치 전처리 API 오류", error=str(exc))
        internal_server_error("배치 전처리 중 오류가 발생했습니다")


# -----------------------------------------------------------------
# 지원 정보 엔드포인트
# -----------------------------------------------------------------


@router.get("/formats", response_model=list[FormatInfo])
async def get_supported_formats() -> list[FormatInfo]:
    """지원 오디오 포맷 정보"""
    formats = [
        FormatInfo(
            extension="wav",
            description="WAV (무손실)",
            supported_codecs=["pcm", "adpcm", "imaadpcm"],
        ),
        FormatInfo(extension="mp3", description="MP3 (압축)", supported_codecs=["mp3", "mpeg"]),
        FormatInfo(extension="flac", description="FLAC (무손실 압축)", supported_codecs=["flac"]),
        FormatInfo(
            extension="aac", description="AAC (고급 압축)", supported_codecs=["aac", "mp4a"]
        ),
        FormatInfo(
            extension="ogg", description="OGG (오픈 포맷)", supported_codecs=["vorbis", "opus"]
        ),
        FormatInfo(extension="m4a", description="M4A (AAC 기반)", supported_codecs=["aac", "mp4a"]),
        FormatInfo(
            extension="wma", description="WMA (Windows Media)", supported_codecs=["wma", "wmav2"]
        ),
        FormatInfo(extension="opus", description="Opus (고효율 코덱)", supported_codecs=["opus"]),
        FormatInfo(
            extension="webm", description="WebM (웹용)", supported_codecs=["opus", "vorbis"]
        ),
    ]
    return formats


@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status() -> ModelStatusResponse:
    """AI 모델 상태 정보"""
    processor = await get_enhanced_processor()

    return ModelStatusResponse(
        ai_noise_removal_enabled=True,
        model_loaded=processor.ai_model.model_loaded,
        supported_formats=len(
            [f for f in ["wav", "mp3", "flac", "aac", "ogg", "m4a", "wma", "opus", "webm"]]
        ),
        batch_max_files=20,
        batch_max_concurrent=5,
        supported_ai_features=["noise_removal", "audio_enhancement"],
        processing_limits={
            "max_file_size_mb": settings.audio_preprocess_max_file_mb,
            "timeout_seconds": 300,
            "max_concurrent_batches": 5,
        },
    )
