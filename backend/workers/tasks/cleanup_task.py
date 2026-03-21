"""
데이터 정리 Celery 태스크 - SPEC-RETENTION-001

REQ-RET-006: Celery Beat 스케줄 - 매일 03:00 실행
"""

from backend.workers.celery_app import celery_app


# @MX:NOTE: Celery Beat 스케줄로 매일 03:00에 자동 실행 (celery_app.py beat_schedule 참고)
@celery_app.task(name="cleanup_expired_data")
def cleanup_expired_data() -> dict:
    """
    만료된 데이터 정리 태스크

    DB 결과 및 임시 파일을 설정된 보존 기간 기준으로 삭제합니다.

    Returns:
        삭제된 DB 레코드 수, 파일 수, 해제된 바이트 크기
    """
    # 지연 임포트: Celery 워커 초기화 시 순환 참조 방지
    from backend.app.config import settings
    from backend.db.sync_engine import get_sync_session
    from backend.services.retention import cleanup_expired_results, cleanup_temp_files

    # DB 만료 레코드 정리 (REQ-RET-003)
    with get_sync_session() as session:
        db_deleted = cleanup_expired_results(session, settings.data_retention_days)

    # 임시 파일 정리 (REQ-RET-004)
    files_deleted, freed = cleanup_temp_files(settings.temp_dir, settings.temp_file_retention_hours)

    return {
        "db_deleted": db_deleted,
        "files_deleted": files_deleted,
        "freed_bytes": freed,
    }
