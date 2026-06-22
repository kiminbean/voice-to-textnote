"""
헬스체크 엔드포인트
REQ-STT-019: /api/v1/health - 서비스 상태, Redis, Celery 워커
REQ-STT-020: /api/v1/health/model - 모델 로드 상태, 메모리
REQ-OPS-008: /api/v1/health/ready - Kubernetes readiness probe
REQ-OPS-009: readiness 체크에서 Redis 연결 및 Celery 워커 가용성 확인
"""

import shutil
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.dependencies import get_diarization_engine, get_redis_client, get_whisper_engine
from backend.app.lifecycle import get_app_started_at
from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.schemas.health import (
    CeleryWorkersStatus,
    DiarizationModelStatusResponse,
    HealthComponents,
    HealthResponse,
    ModelStatusResponse,
)
from backend.utils.logger import get_logger
from backend.workers.celery_app import celery_app

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
        ping_result = redis_client.ping()
        if hasattr(ping_result, "__await__"):
            await ping_result
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

    # REQ-LIFE-006: 시작 시각 및 업타임 계산
    app_started_at = get_app_started_at()
    started_at_iso: str | None = app_started_at.isoformat() if app_started_at else None
    uptime_seconds: float = (
        (datetime.now(UTC) - app_started_at).total_seconds() if app_started_at else 0
    )

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
        started_at=started_at_iso,
        uptime_seconds=uptime_seconds,
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


@router.get("/diarization", response_model=DiarizationModelStatusResponse)
async def diarization_model_health(
    engine: DiarizationEngine = Depends(get_diarization_engine),
) -> DiarizationModelStatusResponse:
    """
    화자 분리 모델 상태 조회
    GET /api/v1/health/diarization
    """
    return DiarizationModelStatusResponse(
        model_name=engine.model_name,
        model_loaded=engine.is_loaded,
        load_time_seconds=engine.load_time_seconds,
    )


@router.get("/ready")
async def readiness_check(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> JSONResponse:
    """
    Kubernetes readiness probe 엔드포인트
    GET /api/v1/health/ready

    REQ-OPS-008: 서비스가 트래픽을 받을 준비가 됐는지 확인
    REQ-OPS-009: Redis 연결 및 Celery 워커 가용성 확인
    - Redis 실패 시 503 반환
    - Celery 워커 없으면 workers=false로 반환하되 200 (개발 환경 허용)
    """
    # Redis 연결 확인 (필수 의존성)
    redis_ok = False
    try:
        ping_result = redis_client.ping()
        if hasattr(ping_result, "__await__"):
            await ping_result
        redis_ok = True
    except Exception as e:
        logger.warning("Readiness 체크: Redis 연결 실패", error=str(e))

    # Celery 워커 가용성 확인 (선택적 의존성 - 개발 환경 허용)
    workers_ok = False
    try:
        # 짧은 타임아웃으로 워커 ping (0.5초)
        inspect = celery_app.control.inspect(timeout=0.5)
        active_workers = inspect.ping()
        workers_ok = bool(active_workers)
    except Exception as e:
        logger.debug("Readiness 체크: Celery 워커 확인 실패 (개발 환경에서 정상)", error=str(e))

    # Redis 실패 시 503, Celery는 개발 환경에서만 선택 의존성으로 허용
    if not redis_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "redis": False,
                "workers": workers_ok,
            },
        )

    if settings.environment == "production" and not workers_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "redis": True,
                "workers": False,
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "redis": True,
            "workers": workers_ok,
        },
    )


async def _check_celery_status(redis_client: aioredis.Redis) -> CeleryWorkersStatus:
    """Celery 워커 실제 상태 확인 (inspect ping + Redis 활성 작업 수)"""
    try:
        # 실제 워커 ping으로 가용성 확인
        inspect = celery_app.control.inspect(timeout=0.5)
        ping_result = inspect.ping()
        worker_count = len(ping_result) if ping_result else 0

        active_count_str = await redis_client.get("active_job_count")
        active_count = int(active_count_str) if active_count_str else 0

        status = "healthy" if worker_count > 0 else "no_workers"
        return CeleryWorkersStatus(
            status=status,
            active_workers=worker_count,
            active_tasks=active_count,
        )
    except Exception as e:
        logger.warning("Celery 상태 조회 실패", error=str(e))
        return CeleryWorkersStatus(
            status=f"unknown: {e}",
            active_workers=0,
            active_tasks=0,
        )
