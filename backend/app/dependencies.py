"""
FastAPI 의존성 주입 - Redis 클라이언트, STT 엔진, 화자 분리 엔진, DB 세션, JWT 인증
"""

import inspect
import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.auth_models import MeetingOwnership, TeamMember
from backend.db.engine import create_engine, get_session_factory
from backend.db.models import TaskResult
from backend.ml.diarization_engine import DiarizationEngine
from backend.ml.stt_engine import WhisperEngine
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# DB 엔진 싱글톤 (설정 기반)
_db_engine = create_engine(database_url=settings.database_url or None)
_session_factory = get_session_factory(_db_engine)


@lru_cache
def get_redis_client() -> aioredis.Redis:
    """Redis 비동기 클라이언트 (싱글톤)"""
    return aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis_client() -> None:
    """캐시된 Redis 클라이언트를 종료하고 싱글톤 캐시를 비운다."""
    if get_redis_client.cache_info().currsize == 0:
        return

    client = get_redis_client()
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result
    get_redis_client.cache_clear()


@lru_cache
def get_whisper_engine() -> WhisperEngine:
    """WhisperEngine 싱글톤 반환"""
    return WhisperEngine.get_instance()


@lru_cache
def get_diarization_engine() -> DiarizationEngine:
    """DiarizationEngine 싱글톤 반환"""
    return DiarizationEngine.get_instance()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    REQ-DB-012: FastAPI DB 세션 의존성

    엔드포인트에 DB 세션을 주입합니다.
    요청 완료 후 세션을 자동으로 닫습니다.

    사용 예:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with _session_factory() as session:
        yield session


def get_request_context(request: Request) -> Request:
    """Expose Request as an optional dependency-friendly value for direct tests."""
    return request


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    SPEC-TEAM-001: JWT Bearer 토큰으로 현재 사용자를 반환하는 의존성

    Authorization: Bearer <access_token> 헤더 필수.

    Raises:
        HTTPException(401): 토큰 없음, 만료, 또는 사용자 없음
    """
    # 지연 임포트로 순환 참조 방지
    from backend.db.auth_models import User
    from backend.services.auth_service import AuthService

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.split(" ", 1)[1]
    auth_service = AuthService()
    payload = auth_service.decode_access_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    import uuid as _uuid

    try:
        user_uuid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    return user


async def get_optional_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Return the current user when a bearer token is present, otherwise None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    if auth_header.startswith("Bearer guest:"):
        return None
    return await get_current_user(request=request, db=db)


def _request_owner_id(request: Request) -> uuid.UUID | None:
    raw_user_id = getattr(request.state, "user_id", None)
    if raw_user_id is None:
        return None
    try:
        return uuid.UUID(str(raw_user_id))
    except ValueError:
        return None


def _request_guest_session_id(request: Request) -> str | None:
    if getattr(request.state, "is_guest", False) is not True:
        return None
    guest_session_id = getattr(request.state, "guest_session_id", None)
    return str(guest_session_id) if guest_session_id else None


def _payload_matches_request(
    request: Request,
    payload: dict | None,
) -> bool:
    if not payload:
        return False

    owner_id = _request_owner_id(request)
    if owner_id is not None and str(payload.get("user_id") or payload.get("owner_id")) == str(
        owner_id
    ):
        return True

    guest_session_id = _request_guest_session_id(request)
    if guest_session_id:
        return bool(
            payload.get("is_guest")
            and str(payload.get("guest_session_id") or "") == guest_session_id
        )

    return False


def _payload_parent_task_ids(payload: dict | None, task_id: str) -> tuple[str, ...]:
    if not payload:
        return ()

    parent_ids: list[str] = []
    for field in (
        "source_task_id",
        "stt_task_id",
        "diarization_task_id",
        "minutes_task_id",
        "summary_task_id",
    ):
        parent_id = payload.get(field)
        if parent_id and str(parent_id) != task_id:
            parent_ids.append(str(parent_id))

    return tuple(dict.fromkeys(parent_ids))


# 파생 task 부모 체인 추적 시 무한 루프를 막는 최대 깊이
# (minutes -> summary -> mind_map 등 보통 1~2단계, 여유를 둬 5단계로 제한)
_MAX_TASK_ACCESS_DEPTH = 5


async def _load_persisted_payload(db: AsyncSession, task_id: str) -> dict | None:
    """DB에 저장된 TaskResult.result_data를 접근 검증용 payload로 로드한다.

    엔드포인트가 payload 없이 require_task_access를 호출하더라도(translation,
    study_pack, keywords 등) 저장된 결과로 payload 매칭과 부모 체인 검증이
    동작하도록 한다. 게스트 귀속 정보(is_guest/guest_session_id)는 일부 파생
    워커가 result_data에 남기지 않으므로 TaskResult 컬럼 값으로 보강한다.
    """
    result = await db.execute(select(TaskResult).where(TaskResult.task_id == task_id))
    record = result.scalar_one_or_none()
    if record is None:
        return None

    payload: dict = dict(record.result_data) if isinstance(record.result_data, dict) else {}
    # 게스트 귀속이 result_data에 누락된 파생 task(sentiment 등)를 위해 컬럼 값 보강
    if record.is_guest and record.guest_session_id:
        payload.setdefault("is_guest", True)
        payload.setdefault("guest_session_id", record.guest_session_id)
    return payload


async def has_task_access(
    request: Request | None,
    db: AsyncSession,
    task_id: str,
    payload: dict | None = None,
    _depth: int = 0,
) -> bool:
    """Return whether the authenticated request may access task_id.

    Development/API-key requests without a user or guest identity keep the
    legacy behavior. User/guest requests must match explicit ownership,
    team sharing, guest session ownership, or an in-flight Redis payload.

    호출자가 payload를 주지 않으면 DB에 저장된 result_data를 로드해 payload
    매칭과 부모 task(minutes_task_id 등) 체인 검증을 수행한다. 이때도 본인이
    해당 task 또는 그 부모를 소유/게스트소유해야만 통과하므로 다른 사용자의
    결과는 여전히 노출되지 않는다(다중 사용자 격리 유지).
    """
    if request is None or not hasattr(request, "state"):
        return True

    owner_id = _request_owner_id(request)
    guest_session_id = _request_guest_session_id(request)
    if owner_id is None and guest_session_id is None:
        return True

    # payload 미전달 시 DB 저장 결과로 보강 (부모 체인/게스트 매칭 활성화)
    if payload is None and _depth < _MAX_TASK_ACCESS_DEPTH:
        payload = await _load_persisted_payload(db, task_id)

    if _payload_matches_request(request, payload):
        return True

    if _depth < _MAX_TASK_ACCESS_DEPTH:
        for parent_task_id in _payload_parent_task_ids(payload, task_id):
            if await has_task_access(
                request=request,
                db=db,
                task_id=parent_task_id,
                _depth=_depth + 1,
            ):
                return True

    if owner_id is not None:
        result = await db.execute(
            select(MeetingOwnership)
            .outerjoin(
                TeamMember,
                (TeamMember.team_id == MeetingOwnership.team_id)
                & (TeamMember.user_id == owner_id),
            )
            .where(
                MeetingOwnership.task_id == task_id,
                (
                    (
                        (MeetingOwnership.owner_id == owner_id)
                        & MeetingOwnership.team_id.is_(None)
                    )
                    | (TeamMember.user_id.is_not(None))
                ),
            )
        )
        return result.scalar_one_or_none() is not None

    if guest_session_id:
        result = await db.execute(
            select(TaskResult).where(
                TaskResult.task_id == task_id,
                TaskResult.is_guest.is_(True),
                TaskResult.guest_session_id == guest_session_id,
            )
        )
        return result.scalar_one_or_none() is not None

    return False


async def require_task_access(
    request: Request | None,
    db: AsyncSession,
    task_id: str,
    payload: dict | None = None,
) -> None:
    """Hide tasks outside the request's ownership boundary behind 404."""
    if not await has_task_access(request=request, db=db, task_id=task_id, payload=payload):
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
