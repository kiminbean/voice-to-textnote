"""
FastAPI 메인 앱
REQ-STT-021: lifespan에서 모델 사전 로드 (warm-up)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import diarization, health, minutes, summary, transcription
from backend.app.config import settings
from backend.app.middleware.rate_limit import setup_rate_limiting
from backend.app.middleware.security_headers import SecurityHeadersMiddleware
from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger, setup_logging

setup_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    서버 시작/종료 이벤트 처리
    시작: 모델 사전 로드 (REQ-STT-021)
    종료: 클린업
    """
    logger.info("서버 시작: 모델 사전 로드 중...")

    # STT 모델 사전 로드 (REQ-STT-021)
    try:
        stt_engine = WhisperEngine.get_instance()
        stt_engine.load(settings.whisper_model)
        logger.info("STT 모델 사전 로드 완료", model=settings.whisper_model)
    except Exception as e:
        logger.error("STT 모델 사전 로드 실패 (서버는 계속 실행)", error=str(e))

    # 화자 분리 모델 사전 로드 (REQ-DIA-011)
    if settings.huggingface_token:
        try:
            dia_engine = DiarizationEngine.get_instance()
            dia_engine.load(
                hf_token=settings.huggingface_token,
                model_name=settings.diarization_model,
            )
            logger.info("화자 분리 모델 사전 로드 완료", model=settings.diarization_model)
        except Exception as e:
            logger.error("화자 분리 모델 사전 로드 실패 (서버는 계속 실행)", error=str(e))
    else:
        logger.warning("HUGGINGFACE_TOKEN 미설정 - 화자 분리 모델 로드 건너뜀")

    yield

    # 종료 시 클린업
    logger.info("서버 종료")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Voice to TextNote - STT API",
        description="Privacy-first automated meeting minutes using local mlx-whisper",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # REQ-SEC-011: 보안 헤더 미들웨어 (가장 먼저 추가 - 모든 응답에 적용)
    app.add_middleware(SecurityHeadersMiddleware)

    # REQ-SEC-009/REQ-SEC-010: CORS (설정 기반 메서드/Origins 제한)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=["*"],
    )

    # REQ-SEC-006/REQ-SEC-007/REQ-SEC-008: Rate Limiting 미들웨어
    setup_rate_limiting(app)

    # 라우터 등록
    api_prefix = "/api/v1"
    app.include_router(transcription.router, prefix=api_prefix)
    app.include_router(diarization.router, prefix=api_prefix)
    app.include_router(minutes.router, prefix=api_prefix)
    app.include_router(summary.router, prefix=api_prefix)
    app.include_router(health.router, prefix=api_prefix)

    return app


app = create_app()
