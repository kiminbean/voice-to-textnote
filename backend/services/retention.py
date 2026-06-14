"""
데이터 보존 정책 서비스 - SPEC-RETENTION-001, SPEC-GUEST-001

REQ-RET-003: 보존 기간 초과 DB 결과 삭제
REQ-RET-004: 보존 기간 초과 임시 파일 삭제
REQ-RET-005: 삭제 수 및 해제 공간 로깅
REQ-GUEST-009: 게스트 데이터 24시간 후 정리
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from backend.db.models import TaskResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# @MX:ANCHOR: DB 만료 레코드 정리 함수 - cleanup_task, admin API에서 호출
# @MX:REASON: fan_in >= 2 (cleanup_task.py, admin.py)
def cleanup_expired_results(session: Session, retention_days: int) -> int:
    """
    보존 기간 초과 DB 결과 삭제

    Args:
        session: SQLAlchemy 동기 세션
        retention_days: 보존 기간 (일)

    Returns:
        삭제된 레코드 수
    """
    # 보존 기간 기준 시각 계산 (타임존 없는 datetime - SQLite 호환)
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)

    stmt = delete(TaskResult).where(TaskResult.created_at < cutoff)
    result = session.execute(stmt)
    session.commit()

    deleted = result.rowcount if isinstance(result, CursorResult) else 0
    # REQ-RET-005: 삭제 수 로깅
    logger.info("만료 결과 정리 완료", deleted_count=deleted, retention_days=retention_days)
    return deleted


# @MX:ANCHOR: 임시 파일 정리 함수 - cleanup_task, admin API에서 호출
# @MX:REASON: fan_in >= 2 (cleanup_task.py, admin.py)
def cleanup_temp_files(temp_dir: Path, retention_hours: int) -> tuple[int, int]:
    """
    보존 기간 초과 임시 파일 삭제

    Args:
        temp_dir: 임시 파일 디렉토리 경로
        retention_hours: 보존 기간 (시간)

    Returns:
        (삭제된 파일 수, 해제된 바이트 크기) 튜플
    """
    cutoff = datetime.now(UTC).timestamp() - (retention_hours * 3600)
    deleted_count = 0
    freed_bytes = 0

    # 디렉토리가 없으면 안전하게 0 반환
    if not temp_dir.exists():
        logger.info("임시 파일 디렉토리 없음 - 정리 건너뜀", temp_dir=str(temp_dir))
        return 0, 0

    for f in temp_dir.iterdir():
        # 파일만 처리 (하위 디렉토리 제외)
        # 동시 정리/재시도 시 다른 프로세스가 먼저 unlink할 수 있으므로 OSError 전반을 흡수한다.
        try:
            stat_result = f.stat()
            if not f.is_file() or stat_result.st_mtime >= cutoff:
                continue
            size = stat_result.st_size
            f.unlink()
        except FileNotFoundError:
            # 다른 워커가 먼저 삭제 — 경쟁 상태이므로 무시
            continue
        except OSError as exc:
            logger.warning(
                "임시 파일 삭제 실패 — 건너뜀",
                path=str(f),
                error=str(exc),
            )
            continue
        deleted_count += 1
        freed_bytes += size

    # REQ-RET-005: 삭제 수 및 해제 공간 로깅
    logger.info(
        "임시 파일 정리 완료",
        deleted_files=deleted_count,
        freed_mb=round(freed_bytes / 1024 / 1024, 2),
    )
    return deleted_count, freed_bytes


def cleanup_guest_data(session: Session, guest_retention_hours: int = 24) -> int:
    """
    REQ-GUEST-009: 게스트 데이터 정리

    is_guest=True이고 보존 기간(기본 24시간)이 지난 task_results를 삭제합니다.
    Redis TTL로 세션이 자동 만료되므로, DB의 게스트 레코드도 주기적으로 정리합니다.

    Args:
        session: SQLAlchemy 동기 세션
        guest_retention_hours: 게스트 데이터 보존 기간 (시간, 기본 24)

    Returns:
        삭제된 레코드 수
    """
    # 게스트 데이터 보존 기간 기준 시각 계산 (타임존 없는 datetime - SQLite 호환)
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=guest_retention_hours)

    stmt = delete(TaskResult).where(
        and_(
            TaskResult.is_guest.is_(True),
            TaskResult.created_at < cutoff,
        )
    )
    result = session.execute(stmt)
    session.commit()

    deleted = result.rowcount if isinstance(result, CursorResult) else 0
    # REQ-RET-005: 삭제 수 로깅
    logger.info(
        "게스트 데이터 정리 완료",
        deleted_count=deleted,
        retention_hours=guest_retention_hours,
    )
    return deleted
