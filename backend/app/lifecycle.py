"""
앱 수명주기 관리 모듈
SPEC-LIFECYCLE-001: 시작 검증, 종료 정리, 버전 정보

REQ-LIFE-001: 시작 시 Redis 연결 검증, 실패 시 warning 로그
REQ-LIFE-002: 시작 시 DB 연결 검증, 개발 모드에서 테이블 자동 생성
REQ-LIFE-003: 구조화된 JSON 시작 로그 출력 (서비스별 상태)
REQ-LIFE-004: 종료 시 DB 커넥션 풀 dispose
REQ-LIFE-005: 종료 완료 로그 출력
"""

from datetime import UTC, datetime

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 앱 시작 시각 (버전 정보 및 uptime 계산용)
# 테스트에서 직접 초기화 가능하도록 모듈 레벨 변수로 관리
_app_started_at: datetime | None = None


def get_app_started_at() -> datetime | None:
    """앱 시작 시각 반환. validate_startup 호출 전에는 None."""
    return _app_started_at


async def validate_startup() -> dict:
    """
    시작 시 의존성 검증, 구조화된 상태 딕셔너리 반환

    REQ-LIFE-001: Redis 연결 검증
    REQ-LIFE-002: DB 연결 검증 + 개발 모드 테이블 생성
    REQ-LIFE-003: 구조화된 JSON 시작 로그
    REQ-ERR2-008: 연결 실패 시 degraded 플래그

    Returns:
        {"redis": "ok"|"warning: ...", "database": "ok"|"warning: ...", "degraded": bool}
    """
    global _app_started_at
    # 시작 시각 기록 (UTC)
    _app_started_at = datetime.now(UTC)

    status: dict[str, str] = {}
    degraded = False

    # REQ-LIFE-001: Redis 연결 검증 - 앱 공유 클라이언트 사용 (연결 누수 방지)
    try:
        from backend.app.dependencies import get_redis_client

        r = get_redis_client()
        await r.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"warning: {e}"
        logger.warning("시작 검증: Redis 연결 실패", error=str(e))
        degraded = True

    # REQ-LIFE-002: DB 연결 검증 + 개발 모드 테이블 자동 생성
    try:
        # SPEC-TEAM-001: auth 모델 import하여 Base.metadata에 등록
        import backend.db.auth_models  # noqa: F401

        # SPEC-BOOKMARK-001: 북마크 모델 import
        import backend.db.bookmark_models  # noqa: F401

        # SPEC-SPEAKER-001: 화자 프로필 모델 import
        import backend.db.speaker_models  # noqa: F401

        # SPEC-TAG-001: 회의록 자동 태깅 모델 import
        import backend.db.tag_models  # noqa: F401

        # SPEC-VERSION-001: 회의록 버전 관리 모델 import
        import backend.db.version_models  # noqa: F401

        # SPEC-WEBHOOK-001: 웹훅 엔드포인트 모델 import
        import backend.db.webhook_models  # noqa: F401

        # BUGFIX: dependencies.py의 동일 엔진 재사용 (별도 엔진 생성 방지)
        # 이전에는 매번 create_engine()을 호출해 실제 사용하는 엔진과 다른 엔진을
        # 생성/폐기했으므로 테이블 생성이 앱 엔진에 반영되지 않았습니다.
        from backend.app.dependencies import _db_engine
        from backend.db.models import Base

        async with _db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"warning: {e}"
        logger.warning("시작 검증: DB 연결 실패", error=str(e))
        degraded = True

    # REQ-LIFE-003: 구조화된 시작 로그 출력
    logger.info("시작 검증 완료", **status, degraded=degraded)

    # REQ-ERR2-008: degraded 플래그 추가
    result = {**status, "degraded": degraded}
    return result


async def cleanup_shutdown() -> None:
    """
    종료 시 리소스 정리

    REQ-LIFE-004: DB 커넥션 풀 dispose (앱 공유 엔진)
    REQ-LIFE-005: 종료 완료 로그
    """
    try:
        from backend.ml.tagging_engine import close_http_client

        await close_http_client()
        logger.info("태깅 HTTP 클라이언트 정리 완료")
    except Exception as e:
        logger.warning("태깅 HTTP 클라이언트 정리 실패", error=str(e))

    try:
        from backend.app.dependencies import close_redis_client

        await close_redis_client()
        logger.info("Redis 클라이언트 정리 완료")
    except Exception as e:
        logger.warning("Redis 클라이언트 정리 실패", error=str(e))

    try:
        # BUGFIX: dependencies.py의 동일 엔진 dispose (별도 엔진 생성 방지)
        from backend.app.dependencies import _db_engine

        await _db_engine.dispose()
        logger.info("DB 커넥션 풀 정리 완료")
    except Exception as e:
        logger.warning("종료 정리 실패", error=str(e))

    # REQ-LIFE-005: 종료 완료 로그
    logger.info("서버 종료 완료")
