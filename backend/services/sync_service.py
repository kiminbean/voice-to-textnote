"""
동기 DB 영속성 서비스 - Celery 워커용

REQ-PERSIST-002: persist_task_result() 동기 메서드
REQ-PERSIST-003: DB 저장 실패 시 예외 전파 금지 (best-effort)

Celery 워커는 동기 환경이므로 동기 세션을 사용합니다.
DB 저장 실패는 WARNING 로그만 남기고 무시합니다.
Redis에 이미 저장되어 있으므로 DB 실패는 치명적이지 않습니다.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.db.auth_models import MeetingOwnership, Team, TeamMember
from backend.db.sync_engine import get_sync_session
from backend.services.team_service import normalize_sharing_policy
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
    owner_id: str | uuid.UUID | None = None,
    source_task_id: str | None = None,
    is_guest: bool = False,
    guest_session_id: str | None = None,
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
        from backend.db.models import TaskResult

        with get_sync_session() as session:
            resolved_guest_session_id = _resolve_guest_session_id(
                session=session,
                is_guest=is_guest,
                guest_session_id=guest_session_id,
                source_task_id=source_task_id,
            )
            resolved_is_guest = resolved_guest_session_id is not None

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
                    is_guest=resolved_is_guest,
                    guest_session_id=resolved_guest_session_id,
                )
                session.add(record)
            else:
                # 기존 레코드 업데이트
                record.task_type = task_type
                record.status = status
                record.result_data = result_data
                record.error_message = error_message
                record.is_guest = resolved_is_guest
                record.guest_session_id = resolved_guest_session_id

            resolved_owner_id = _resolve_owner_id(
                session=session,
                owner_id=owner_id,
                source_task_id=source_task_id,
            )
            if resolved_owner_id is not None:
                _ensure_owner_and_default_team_shares(
                    session=session,
                    task_id=task_id,
                    owner_id=resolved_owner_id,
                )

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


def _resolve_owner_id(session, owner_id: str | uuid.UUID | None, source_task_id: str | None):
    if owner_id:
        try:
            return owner_id if isinstance(owner_id, uuid.UUID) else uuid.UUID(str(owner_id))
        except ValueError:
            logger.warning("잘못된 owner_id 형식 - 소유권 저장 생략", owner_id=str(owner_id))
            return None

    if not source_task_id:
        return None

    ownership = (
        session.execute(
            select(MeetingOwnership)
            .where(
                MeetingOwnership.task_id == source_task_id,
                MeetingOwnership.team_id.is_(None),
            )
            .order_by(MeetingOwnership.created_at.asc())
        )
        .scalars()
        .first()
    )
    return ownership.owner_id if ownership is not None else None


def _resolve_guest_session_id(
    session,
    is_guest: bool,
    guest_session_id: str | None,
    source_task_id: str | None,
) -> str | None:
    if is_guest and guest_session_id:
        return guest_session_id

    if not source_task_id:
        return None

    from backend.db.models import TaskResult

    source = session.execute(
        select(TaskResult).where(TaskResult.task_id == source_task_id)
    ).scalar_one_or_none()
    if source is not None and source.is_guest and source.guest_session_id:
        return source.guest_session_id
    return None


def _ensure_owner_and_default_team_shares(session, task_id: str, owner_id: uuid.UUID) -> None:
    existing_owner = session.execute(
        select(MeetingOwnership).where(
            MeetingOwnership.task_id == task_id,
            MeetingOwnership.owner_id == owner_id,
            MeetingOwnership.team_id.is_(None),
        )
    ).scalar_one_or_none()
    if existing_owner is None:
        session.add(
            MeetingOwnership(
                id=uuid.uuid4(),
                task_id=task_id,
                owner_id=owner_id,
                team_id=None,
                shared_at=None,
            )
        )

    teams = (
        session.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == owner_id)
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for team in teams:
        if normalize_sharing_policy(team.sharing_policy)["default_visibility"] != "team_default":
            continue
        existing_share = session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.team_id == team.id,
            )
        ).scalar_one_or_none()
        if existing_share is not None:
            continue
        session.add(
            MeetingOwnership(
                id=uuid.uuid4(),
                task_id=task_id,
                owner_id=owner_id,
                team_id=team.id,
                shared_at=now,
            )
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
