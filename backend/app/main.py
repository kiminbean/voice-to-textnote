"""
FastAPI 메인 앱
REQ-STT-021: lifespan에서 모델 사전 로드 (warm-up)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.db.quality_feedback_models  # noqa: F401

# SPEC-SPEAKER-VOICE-001 / SPEC-QUALITY-MONITOR-001: 신규 모델을 Base.metadata에 등록
import backend.db.speaker_voice_models  # noqa: F401
from backend.app.api.v1.registry import ROUTER_REGISTRY
from backend.app.config import settings
from backend.app.error_handlers import register_exception_handlers
from backend.app.lifecycle import cleanup_shutdown, validate_startup
from backend.app.metrics import setup_metrics
from backend.app.middleware.audit_log import AuditLogMiddleware
from backend.app.middleware.auth import verify_api_key
from backend.app.middleware.rate_limit import setup_rate_limiting
from backend.app.middleware.request_id import RequestIDMiddleware
from backend.app.middleware.security_headers import SecurityHeadersMiddleware
from backend.app.middleware.validators import PathValidationMiddleware
from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger, setup_logging

setup_logging(settings.log_level)
logger = get_logger(__name__)


TAGS_METADATA = [
    {"name": "health", "description": "Service liveness, readiness, and version checks."},
    {"name": "batch", "description": "Batch transcription submission and status APIs."},
    {"name": "transcriptions", "description": "Audio upload, STT processing, and result retrieval."},
    {"name": "diarizations", "description": "Speaker diarization task submission and results."},
    {"name": "minutes", "description": "Structured meeting minutes generation and retrieval."},
    {"name": "summaries", "description": "AI summary generation from meeting minutes."},
    {"name": "stream", "description": "Server-sent task progress updates."},
    {"name": "history", "description": "Stored task history lookup and deletion."},
    {"name": "admin", "description": "Operational maintenance endpoints."},
    {"name": "templates", "description": "Meeting minutes template upload and management."},
    {"name": "search", "description": "Full-text meeting search."},
    {"name": "export", "description": "Meeting export endpoints."},
    {"name": "statistics", "description": "Meeting statistics and dashboard views."},
    {"name": "quality", "description": "Meeting minutes quality assessment and improvement suggestions."},
    {"name": "calendar", "description": "Calendar integration for meeting events and action items."},
    {"name": "auth", "description": "User authentication and session APIs."},
    {"name": "devices", "description": "FCM device registration and push notification management."},
    {"name": "teams", "description": "Team workspace management."},
    {"name": "meetings", "description": "Shared meeting records and permissions."},
    {"name": "bookmarks", "description": "Meeting bookmarks and highlights."},
    {"name": "speakers", "description": "Speaker profile management."},
    {"name": "webhooks", "description": "Webhook endpoint management."},
    {"name": "versions", "description": "Meeting minutes version history."},
    {"name": "sentiment", "description": "Meeting sentiment analysis."},
    {"name": "tags", "description": "Automatic meeting tags and tag management."},
    {"name": "keywords", "description": "Automatic keyword extraction and recommendation."},
    {"name": "action-items", "description": "Action item extraction from meeting text."},
    {"name": "audio-analysis", "description": "Audio quality analysis."},
    {"name": "audio-preprocess", "description": "Audio cleanup and normalization."},
    {"name": "advanced-search", "description": "Advanced search with filters, analytics, and history."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    서버 시작/종료 이벤트 처리
    시작: 모델 사전 로드 (REQ-STT-021)
    종료: 클린업
    """
    logger.info("서버 시작: 모델 사전 로드 중...")

    # SPEC-LIFECYCLE-001: 시작 시 의존성 검증 (Redis, DB)
    await validate_startup()

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
    # SPEC-LIFECYCLE-001: 종료 시 리소스 정리 (DB 커넥션 풀 dispose)
    await cleanup_shutdown()


def create_app() -> FastAPI:
    # FIX-SEC-003: 프로덕션 환경에서 Swagger/ReDoc UI 비활성화
    docs_url = "/docs" if settings.environment != "production" else None
    redoc_url = "/redoc" if settings.environment != "production" else None

    app = FastAPI(
        title="Voice to TextNote - STT API",
        description="Privacy-first automated meeting minutes using local mlx-whisper",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_tags=TAGS_METADATA,
    )

    # REQ-ERR-003 ~ REQ-ERR-006: 전역 예외 핸들러 등록 (가장 먼저 등록)
    register_exception_handlers(app)

    # REQ-OPS-001/002: Prometheus 메트릭스 계측 (라우터 등록 전에 설정)
    setup_metrics(app)

    # REQ-OPS-005/006/007: Request ID 미들웨어
    app.add_middleware(RequestIDMiddleware)

    # SPEC-LOG-001: 감사 로깅 미들웨어 (RequestID 이후, SecurityHeaders 이전)
    app.add_middleware(AuditLogMiddleware)

    # REQ-SEC-011: 보안 헤더 미들웨어 (가장 먼저 추가 - 모든 응답에 적용)
    app.add_middleware(SecurityHeadersMiddleware)

    # FIX-SEC-004: 경로 파라미터 유효성 검증 (경로 탐색 공격 방지)
    app.add_middleware(PathValidationMiddleware)

    # REQ-SEC-009/REQ-SEC-010: CORS (설정 기반 메서드/Origins 제한)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=["X-API-Key", "Content-Type", "Accept", "X-Request-ID"],
    )

    # REQ-SEC-006/REQ-SEC-007/REQ-SEC-008: Rate Limiting 미들웨어
    setup_rate_limiting(app)

    # 라우터 등록
    # REQ-SEC-001~003: verify_api_key 의존성을 보호 대상 라우터에 적용.
    # 등록 순서와 인증 정책은 registry.py의 ROUTER_REGISTRY가 SSOT.
    # (배치→transcription 순서, 각 라우터의 requires_api_key 플래그 등)
    api_prefix = "/api/v1"
    _auth = [Depends(verify_api_key)]
    for router, requires_api_key in ROUTER_REGISTRY:
        app.include_router(
            router,
            prefix=api_prefix,
            dependencies=_auth if requires_api_key else None,
        )

    return app


app = create_app()
