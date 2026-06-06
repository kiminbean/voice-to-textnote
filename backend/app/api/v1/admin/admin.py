"""
Admin API 라우터 - SPEC-RETENTION-001

REQ-RET-007: POST /api/v1/admin/cleanup - 즉시 정리 실행 및 결과 반환
"""

from fastapi import APIRouter

from backend.app.config import settings
from backend.db.sync_engine import get_sync_session
from backend.services.retention import cleanup_expired_results, cleanup_temp_files
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# @MX:ANCHOR: 즉시 정리 엔드포인트 - Celery 없이 동기 실행
# @MX:REASON: 외부 시스템 연동 진입점 (DB + 파일시스템)
@router.post("/cleanup", status_code=200)
async def trigger_cleanup() -> dict:
    """
    데이터 보존 정책 즉시 실행

    Celery 스케줄을 기다리지 않고 즉시 정리 작업을 수행합니다.

    Returns:
        삭제된 DB 레코드 수, 파일 수, 해제된 바이트 크기
    """
    logger.info(
        "즉시 데이터 정리 시작",
        retention_days=settings.data_retention_days,
        retention_hours=settings.temp_file_retention_hours,
    )

    # DB 만료 레코드 정리
    with get_sync_session() as session:
        db_deleted = cleanup_expired_results(session, settings.data_retention_days)

    # 임시 파일 정리
    files_deleted, freed_bytes = cleanup_temp_files(
        settings.temp_dir, settings.temp_file_retention_hours
    )

    logger.info(
        "즉시 데이터 정리 완료",
        db_deleted=db_deleted,
        files_deleted=files_deleted,
        freed_bytes=freed_bytes,
    )

    return {
        "db_deleted": db_deleted,
        "files_deleted": files_deleted,
        "freed_bytes": freed_bytes,
    }
