"""
헬스체크 엔드포인트
REQ-STT-019: /api/v1/health - 서비스 상태, Redis, Celery 워커
REQ-STT-020: /api/v1/health/model - 모델 로드 상태, 메모리
"""

import shutil
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_redis_client, get_whisper_engine
from backend.ml.stt_engine import WhisperEngine
from backend.schemas.health import (
    CeleryWorkersStatus,
    HealthComponents,
    HealthResponse,
    ModelStatusResponse,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

APP_VERSION = "0.1.0"


@router.get("", response_model=HealthResponse)
async def health_check(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> HealthResponse:
    """
    서비스 전체 헬스체크
    GET /api/v1/health
    """
    # Redis 연결 확인
    redis_status = "healthy"
    try:
        await redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {e}"
        logger.warning("Redis 연결 실패", error=str(e))

    # Celery 워커 상태 (Redis를 통해 간접 확인)
    celery_status = await _check_celery_status(redis_client)

    # ffmpeg 설치 확인
    ffmpeg_status = "available" if shutil.which("ffmpeg") else "unavailable"
    if ffmpeg_status == "unavailable":
        logger.warning("ffmpeg 미설치 감지")

    # 전체 상태 판단
    overall = "healthy"
    if redis_status != "healthy":
        overall = "degraded"
    if ffmpeg_status == "unavailable":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        version=APP_VERSION,
        components=HealthComponents(
            api="healthy",
            redis=redis_status,
            celery_workers=celery_status,
            ffmpeg=ffmpeg_status,
        ),
        timestamp=datetime.now(UTC),
    )


@router.get("/model", response_model=ModelStatusResponse)
async def model_health(
    engine: WhisperEngine = Depends(get_whisper_engine),
) -> ModelStatusResponse:
    """
    모델 상태 조회
    GET /api/v1/health/model
    """
    memory_info = engine.get_memory_info()

    return ModelStatusResponse(
        model_name=engine.model_name,
        model_loaded=engine.is_loaded,
        device=engine.device if engine.is_loaded else None,
        memory_usage_mb=round(memory_info["used_mb"], 1),
        total_system_memory_mb=round(memory_info["total_mb"], 1),
        available_memory_mb=round(memory_info["available_mb"], 1),
        load_time_seconds=engine.load_time_seconds,
        version="0.4.3+",
    )


async def _check_celery_status(redis_client: aioredis.Redis) -> CeleryWorkersStatus:
    """Redis에서 활성 작업 수 조회로 Celery 상태 간접 확인"""
    try:
        active_count_str = await redis_client.get("active_job_count")
        active_count = int(active_count_str) if active_count_str else 0
        return CeleryWorkersStatus(
            status="healthy",
            active_workers=1,  # 단순화: 워커 프로세스 1개 가정
            active_tasks=active_count,
        )
    except Exception as e:
        logger.warning("Celery 상태 조회 실패", error=str(e))
        return CeleryWorkersStatus(
            status=f"unknown: {e}",
            active_workers=0,
            active_tasks=0,
        )
