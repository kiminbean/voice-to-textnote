"""
FastAPI 메인 앱
REQ-STT-021: lifespan에서 모델 사전 로드 (warm-up)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import health, transcription
from backend.app.config import settings
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
    try:
        engine = WhisperEngine.get_instance()
        engine.load(settings.whisper_model)
        logger.info("모델 사전 로드 완료", model=settings.whisper_model)
    except Exception as e:
        # 모델 로드 실패 시 서버는 계속 실행 (health endpoint에서 미로드 상태 보고)
        logger.error("모델 사전 로드 실패 (서버는 계속 실행)", error=str(e))

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

    # CORS (로컬 전용 서비스)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    api_prefix = "/api/v1"
    app.include_router(transcription.router, prefix=api_prefix)
    app.include_router(health.router, prefix=api_prefix)

    return app


app = create_app()
