"""
앱 수명주기 관리 모듈
SPEC-LIFECYCLE-001: 시작 검증, 종료 정리, 버전 정보

REQ-LIFE-001: 시작 시 Redis 연결 검증, 실패 시 warning 로그
REQ-LIFE-002: 시작 시 DB 연결 검증, 개발 모드에서 테이블 자동 생성
REQ-LIFE-003: 구조화된 JSON 시작 로그 출력 (서비스별 상태)
REQ-LIFE-004: 종료 시 DB 커넥션 풀 dispose
REQ-LIFE-005: 종료 완료 로그 출력
"""

from datetime import datetime, timezone

from backend.db.engine import create_engine
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

    Returns:
        {"redis": "ok"|"warning: ...", "database": "ok"|"warning: ..."}
    """
    global _app_started_at
    # 시작 시각 기록 (UTC)
    _app_started_at = datetime.now(timezone.utc)

    status: dict[str, str] = {}

    # REQ-LIFE-001: Redis 연결 검증
    try:
        import redis.asyncio as aioredis

        from backend.app.config import settings

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"warning: {e}"
        logger.warning("시작 검증: Redis 연결 실패", error=str(e))

    # REQ-LIFE-002: DB 연결 검증 + 개발 모드 테이블 자동 생성
    try:
        from backend.app.config import settings
        from backend.db.models import Base

        engine = create_engine(settings.database_url or None)

        # 개발 모드(SQLite 폴백): 테이블 자동 생성
        if not settings.database_url:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"warning: {e}"
        logger.warning("시작 검증: DB 연결 실패", error=str(e))

    # REQ-LIFE-003: 구조화된 시작 로그 출력
    logger.info("시작 검증 완료", **status)

    return status


async def cleanup_shutdown() -> None:
    """
    종료 시 리소스 정리

    REQ-LIFE-004: DB 커넥션 풀 dispose
    REQ-LIFE-005: 종료 완료 로그
    """
    try:
        from backend.app.config import settings

        engine = create_engine(settings.database_url or None)
        await engine.dispose()
        logger.info("DB 커넥션 풀 정리 완료")
    except Exception as e:
        logger.warning("종료 정리 실패", error=str(e))

    # REQ-LIFE-005: 종료 완료 로그
    logger.info("서버 종료 완료")
