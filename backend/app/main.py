"""
FastAPI 메인 앱
REQ-STT-021: lifespan에서 모델 사전 로드 (warm-up)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import (
    admin,
    auth,
    batch,
    bookmarks,
    dashboard,
    diarization,
    export,
    health,
    history,
    meetings,
    minutes,
    search,
    speakers,
    statistics,
    stream,
    summary,
    tags,
    teams,
    templates,
    transcription,
    versions,
    webhooks,
    sentiment,
)
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
    # REQ-SEC-001~003: verify_api_key 의존성을 보호 대상 라우터에 적용
    # health 라우터는 인증 불필요 (헬스체크, /metrics, /docs, /redoc 포함)
    api_prefix = "/api/v1"
    _auth = [Depends(verify_api_key)]
    # 배치 라우터는 /transcriptions/{task_id} 경로 충돌 방지를 위해 transcription보다 먼저 등록
    app.include_router(batch.router, prefix=api_prefix, dependencies=_auth)
    app.include_router(transcription.router, prefix=api_prefix, dependencies=_auth)
    app.include_router(diarization.router, prefix=api_prefix, dependencies=_auth)
    app.include_router(minutes.router, prefix=api_prefix, dependencies=_auth)
    app.include_router(summary.router, prefix=api_prefix, dependencies=_auth)
    app.include_router(health.router, prefix=api_prefix)
    # REQ-SSE-001: 태스크 상태 실시간 스트리밍 엔드포인트
    app.include_router(stream.router, prefix=api_prefix, dependencies=_auth)
    # SPEC-HISTORY-001: 작업 이력 조회/삭제 엔드포인트
    app.include_router(history.router, prefix=api_prefix, dependencies=_auth)
    # SPEC-RETENTION-001: 데이터 보존 정책 즉시 실행 엔드포인트
    app.include_router(admin.router, prefix=api_prefix, dependencies=_auth)
    # REQ-TMPL-001/003: 회의록 양식 관리 엔드포인트
    app.include_router(templates.router, prefix=api_prefix, dependencies=_auth)
    # SPEC-SEARCH-001: 회의록 전문 검색 엔드포인트
    app.include_router(search.router, prefix=api_prefix, dependencies=_auth)
    # SPEC-EXPORT-001: 회의록 PDF 내보내기 엔드포인트
    app.include_router(export.router, prefix=api_prefix, dependencies=_auth)
    # SPEC-STATS-001: 회의 통계 대시보드 엔드포인트 (읽기 전용)
    app.include_router(statistics.router, prefix=api_prefix, dependencies=_auth)
       # SPEC-STATS-002: 전체 회의 통계 대시보드 엔드포인트 (읽기 전용)
    app.include_router(dashboard.router, prefix=api_prefix, dependencies=_auth)

    # SPEC-TEAM-001: 인증 API (공개 엔드포인트 - API Key 불필요)
    app.include_router(auth.router, prefix=api_prefix)

    # SPEC-TEAM-001: 팀 관리 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(teams.router, prefix=api_prefix)

    # SPEC-TEAM-001 REQ-TEAM-005: 회의록 공유 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(meetings.router, prefix=api_prefix)

    # SPEC-BOOKMARK-001: 북마크/하이라이트 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(bookmarks.router, prefix=api_prefix)

    # SPEC-SPEAKER-001: 화자 프로필 관리 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(speakers.router, prefix=api_prefix)

    # SPEC-WEBHOOK-001: 웹훅 엔드포인트 관리 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(webhooks.router, prefix=api_prefix)

    # SPEC-VERSION-001: 회의록 버전 관리 API (JWT 인증은 각 엔드포인트에서 처리)
    app.include_router(versions.router, prefix=api_prefix)

    app.include_router(sentiment.router, prefix=api_prefix, dependencies=_auth)

    # SPEC-TAG-001: 회의록 자동 태깅
    app.include_router(tags.router, prefix=api_prefix, dependencies=_auth)

    return app


app = create_app()
