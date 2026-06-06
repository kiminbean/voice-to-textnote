"""
동기 DB 영속성 서비스 - Celery 워커용

REQ-PERSIST-002: persist_task_result() 동기 메서드
REQ-PERSIST-003: DB 저장 실패 시 예외 전파 금지 (best-effort)

Celery 워커는 동기 환경이므로 동기 세션을 사용합니다.
DB 저장 실패는 WARNING 로그만 남기고 무시합니다.
Redis에 이미 저장되어 있으므로 DB 실패는 치명적이지 않습니다.
"""

from backend.db.sync_engine import get_sync_session
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# SPEC-SEARCH-001: 검색 인덱스 자동 업데이트 대상 타입
_INDEXABLE_TASK_TYPES = {"minutes", "summary"}


def persist_task_result(
    task_id: str,
    task_type: str,
    status: str,
    result_data: dict | None = None,
    error_message: str | None = None,
) -> None:
    """
    Celery 작업 결과를 DB에 best-effort 방식으로 저장

    DB 저장 실패 시 예외를 전파하지 않습니다 (REQ-PERSIST-003).
    Redis에 이미 저장된 데이터이므로 DB 실패는 무시해도 안전합니다.

    Args:
        task_id: Celery 작업 ID
        task_type: 작업 유형 (transcription, diarization, minutes, summary)
        status: 작업 상태 (pending, processing, completed, failed)
        result_data: 결과 데이터 (JSON 직렬화 가능한 dict)
        error_message: 오류 메시지 (실패 시)
    """
    try:
        from sqlalchemy import select

        from backend.db.models import TaskResult

        with get_sync_session() as session:
            # 기존 레코드 조회 (upsert 지원)
            stmt = select(TaskResult).where(TaskResult.task_id == task_id)
            record = session.execute(stmt).scalar_one_or_none()

            if record is None:
                # 신규 레코드 삽입
                record = TaskResult(
                    task_id=task_id,
                    task_type=task_type,
                    status=status,
                    result_data=result_data,
                    error_message=error_message,
                )
                session.add(record)
            else:
                # 기존 레코드 업데이트
                record.task_type = task_type
                record.status = status
                record.result_data = result_data
                record.error_message = error_message

            session.commit()

        # SPEC-SEARCH-001: 검색 인덱스 자동 업데이트 (best-effort)
        _try_index_search_entry(task_id, task_type, result_data)

    except Exception as e:
        # REQ-PERSIST-003: DB 저장 실패는 무시 (작업에 영향 없음)
        logger.warning(
            "DB 결과 저장 실패 (무시)",
            task_id=task_id,
            task_type=task_type,
            error=str(e),
        )


def _try_index_search_entry(
    task_id: str,
    task_type: str,
    result_data: dict | None,
) -> None:
    """
    SPEC-SEARCH-001: 검색 인덱스 자동 업데이트 헬퍼 (best-effort)

    minutes, summary 타입만 처리합니다.
    별도 세션을 열어 FTS5 테이블에 인덱싱합니다.
    모든 예외를 캐치하여 persist에 영향을 주지 않습니다.

    Args:
        task_id: 작업 ID
        task_type: 작업 유형
        result_data: 결과 데이터
    """
    # 인덱싱 대상 타입이 아니면 스킵
    if task_type not in _INDEXABLE_TASK_TYPES:
        return

    if not result_data:
        return

    try:
        from backend.db.search_models import ensure_search_index_table, index_search_entry
        from backend.db.sync_engine import get_sync_session

        with get_sync_session() as session:
            # FTS5 테이블 존재 확인 (없으면 생성)
            from backend.db.sync_engine import _get_sync_engine

            engine, _ = _get_sync_engine()
            ensure_search_index_table(engine)

            # 검색 인덱스에 추가
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type=task_type,
                result_data=result_data,
            )
            session.commit()

    except Exception as e:
        # best-effort: 인덱싱 실패는 경고만 로그
        logger.warning(
            "검색 인덱스 자동 업데이트 실패 (무시)",
            task_id=task_id,
            task_type=task_type,
            error=str(e),
        )
