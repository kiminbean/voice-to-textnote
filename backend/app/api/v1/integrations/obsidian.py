"""SPEC-OBSIDIAN-001: Obsidian 연계 API 엔드포인트."""

from __future__ import annotations

import json
from inspect import isawaitable
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import (
    get_current_user,
    get_db_session,
    get_redis_client,
    get_request_context,
    require_task_access,
)
from backend.app.errors import bad_request, not_found, service_unavailable
from backend.db.models import TaskResult
from backend.db.obsidian_models import ObsidianConfig
from backend.db.sync_engine import get_sync_session
from backend.schemas.obsidian import (
    ObsidianConfigRequest,
    ObsidianConfigResponse,
    ObsidianExportResponse,
    ObsidianValidateRequest,
    ObsidianValidateResponse,
)
from backend.services.obsidian_service import obsidian_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


def _dependency_placeholder(value: Any) -> bool:
    return value.__class__.__name__ == "Depends"


def _current_user_id(current_user: Any) -> str | None:
    if current_user is None or _dependency_placeholder(current_user):
        return None
    user_id = getattr(current_user, "id", None)
    return str(user_id) if user_id is not None else None


def _attach_user_to_request(request: Any, user_id: str | None) -> None:
    if not user_id or request is None or _dependency_placeholder(request):
        return
    state = getattr(request, "state", None)
    if state is not None and getattr(state, "user_id", None) is None:
        state.user_id = user_id


def _usable_db(db: Any) -> Any | None:
    return None if db is None or _dependency_placeholder(db) else db


def _get_config_from_db(
    *,
    user_id: str | None = None,
    team_id: str | None = None,
) -> ObsidianConfig | None:
    """DB에서 Obsidian 설정 조회. 인증 사용자 요청은 사용자 scope로 격리한다."""
    try:
        with get_sync_session() as session:
            stmt = select(ObsidianConfig)
            if user_id is not None:
                stmt = stmt.where(ObsidianConfig.user_id == str(user_id))
            if team_id is not None:
                stmt = stmt.where(ObsidianConfig.team_id == str(team_id))
            stmt = stmt.order_by(ObsidianConfig.updated_at.desc()).limit(1)
            return session.scalars(stmt).first()
    except Exception as e:
        logger.warning("DB에서 Obsidian 설정 조회 실패", error=str(e))
        return None


def _save_config_to_db(
    req: ObsidianConfigRequest,
    vault_name: str,
    *,
    user_id: str | None = None,
    team_id: str | None = None,
) -> ObsidianConfig:
    """설정 저장 (기존 있으면 업데이트, 없으면 생성)."""
    from sqlalchemy import select

    with get_sync_session() as session:
        stmt = select(ObsidianConfig)
        if user_id is not None:
            stmt = stmt.where(ObsidianConfig.user_id == str(user_id))
        if team_id is not None:
            stmt = stmt.where(ObsidianConfig.team_id == str(team_id))
        stmt = stmt.order_by(ObsidianConfig.updated_at.desc()).limit(1)
        existing = session.scalars(stmt).first()

        if existing:
            existing.user_id = str(user_id) if user_id is not None else existing.user_id
            existing.team_id = str(team_id) if team_id is not None else existing.team_id
            existing.vault_path = req.vault_path
            existing.vault_name = vault_name
            existing.folder_pattern = req.folder_pattern
            existing.filename_pattern = req.filename_pattern
            existing.auto_export = req.auto_export
            existing.conflict_policy = req.conflict_policy
            existing.frontmatter_custom = req.frontmatter_custom
            existing.note_template_id = req.note_template_id
            session.commit()
            session.refresh(existing)
            return existing
        else:
            cfg = ObsidianConfig(
                user_id=str(user_id) if user_id is not None else None,
                team_id=str(team_id) if team_id is not None else None,
                vault_path=req.vault_path,
                vault_name=vault_name,
                folder_pattern=req.folder_pattern,
                filename_pattern=req.filename_pattern,
                auto_export=req.auto_export,
                conflict_policy=req.conflict_policy,
                frontmatter_custom=req.frontmatter_custom,
                note_template_id=req.note_template_id,
            )
            session.add(cfg)
            session.commit()
            session.refresh(cfg)
            return cfg


def _config_to_response(cfg: ObsidianConfig | None) -> ObsidianConfigResponse:
    if cfg is None:
        return ObsidianConfigResponse(
            vault_path="",
            vault_name="",
            vault_valid=False,
            folder_pattern="Voice-to-TextNote/{{date}}",
            filename_pattern="{{date}}_{{title}}",
            auto_export=False,
            conflict_policy="overwrite",
        )
    validation = obsidian_service.validate_vault(cfg.vault_path)
    return ObsidianConfigResponse(
        vault_path=cfg.vault_path,
        vault_name=cfg.vault_name,
        vault_valid=validation["valid"],
        folder_pattern=cfg.folder_pattern,
        filename_pattern=cfg.filename_pattern,
        auto_export=cfg.auto_export,
        conflict_policy=cfg.conflict_policy,
        frontmatter_custom=cfg.frontmatter_custom,
        note_template_id=cfg.note_template_id,
    )


@router.post("/validate", response_model=ObsidianValidateResponse)
async def validate_vault(req: ObsidianValidateRequest) -> ObsidianValidateResponse:
    """REQ-OBS-001: Vault 경로 검증."""
    result = obsidian_service.validate_vault(req.vault_path)
    return ObsidianValidateResponse(**result)


@router.get("/config", response_model=ObsidianConfigResponse)
async def get_config(current_user=Depends(get_current_user)) -> ObsidianConfigResponse:
    """설정 조회."""
    cfg = _get_config_from_db(user_id=_current_user_id(current_user))
    return _config_to_response(cfg)


@router.post("/config", response_model=ObsidianConfigResponse)
async def save_config(
    req: ObsidianConfigRequest,
    current_user=Depends(get_current_user),
) -> ObsidianConfigResponse:
    """REQ-OBS-012: 설정 저장 및 검증."""
    if _has_traversal(req.vault_path):
        bad_request("경로 탐색 패턴이 감지되었습니다", error_code="PATH_TRAVERSAL_DETECTED")

    if _has_traversal(req.folder_pattern):
        bad_request(
            "folder_pattern에 경로 탐색 패턴이 감지되었습니다",
            error_code="PATH_TRAVERSAL_DETECTED",
        )

    if _has_traversal(req.filename_pattern):
        bad_request(
            "filename_pattern에 경로 탐색 패턴이 감지되었습니다",
            error_code="PATH_TRAVERSAL_DETECTED",
        )

    validation = obsidian_service.validate_vault(req.vault_path)
    if not validation["valid"]:
        if validation["is_symlink"]:
            bad_request(
                "심볼릭 링크 경로는 허용되지 않습니다",
                error_code="SYMLINK_VAULT_DETECTED",
            )
        bad_request(
            "유효하지 않은 vault 경로입니다 (.obsidian 폴더가 없거나 쓰기 권한이 없습니다)",
            error_code="INVALID_VAULT_PATH",
        )

    if req.conflict_policy not in ("overwrite", "skip"):
        bad_request("conflict_policy는 'overwrite' 또는 'skip'이어야 합니다")

    cfg = _save_config_to_db(
        req,
        validation["vault_name"],
        user_id=_current_user_id(current_user),
    )
    logger.info("Obsidian 설정 저장", vault=validation["vault_name"])
    return _config_to_response(cfg)


@router.post("/export/{meeting_id}", response_model=ObsidianExportResponse)
async def export_meeting(
    meeting_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    request = Depends(get_request_context),
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ObsidianExportResponse:
    """REQ-OBS-006: 회의 내용을 vault에 마크다운 노트로 export."""
    user_id = _current_user_id(current_user)
    _attach_user_to_request(request, user_id)
    db_session = _usable_db(db)

    cfg = _get_config_from_db(user_id=user_id)
    if cfg is None or not cfg.vault_path:
        service_unavailable(
            "Obsidian vault 경로가 설정되지 않았습니다",
            error_code="OBSIDIAN_NOT_CONFIGURED",
        )

    validation = obsidian_service.validate_vault(cfg.vault_path)
    if not validation["valid"]:
        service_unavailable(
            "Obsidian vault 경로가 유효하지 않습니다",
            error_code="OBSIDIAN_VAULT_INVALID",
        )

    (
        meeting_data,
        minutes_data,
        summary_data,
        sentiment_data,
        tone_data,
    ) = await _gather_meeting_data(meeting_id, redis_client, db=db_session)
    study_pack_data = await _find_cached_study_pack(redis_client, meeting_id)
    mind_map_data = await _find_cached_mind_map(redis_client, summary_data)
    sales_brief_data = await _find_cached_sales_brief(
        redis_client,
        meeting_id,
        db=db_session,
    )

    if not meeting_data:
        not_found(f"회의를 찾을 수 없습니다: meeting_id={meeting_id}")

    if db_session is not None:
        await require_task_access(request, db_session, meeting_id, minutes_data)

    try:
        file_path = obsidian_service.compute_file_path(
            cfg.vault_path,
            cfg.folder_pattern,
            cfg.filename_pattern,
            meeting_data,
        )
    except ValueError as e:
        msg = str(e)
        if "탐색" in msg or "traversal" in msg.lower():
            bad_request(msg, error_code="PATH_TRAVERSAL_DETECTED")
        bad_request(msg)

    note_content = obsidian_service.compose_note(
        meeting_data,
        minutes_data,
        summary_data,
        sentiment_data,
        tone_data,
        study_pack_data=study_pack_data,
        mind_map_data=mind_map_data,
        sales_brief_data=sales_brief_data,
        frontmatter_custom=cfg.frontmatter_custom,
    )

    try:
        written = obsidian_service.atomic_write(
            file_path,
            note_content,
            exist_ok=(cfg.conflict_policy != "skip"),
        )
    except OSError as e:
        logger.error("Obsidian 노트 파일 쓰기 실패", error=str(e), path=str(file_path))
        return ObsidianExportResponse(success=False, error=f"파일 쓰기 실패: {e}")

    uri = obsidian_service.build_obsidian_uri(cfg.vault_path, file_path)
    rel_path = str(file_path.resolve().relative_to(_vault_resolved(cfg.vault_path)))

    if not written:
        logger.info(
            "Obsidian export 건너뜀 (skip 정책)",
            meeting_id=meeting_id,
            file_path=str(file_path),
        )
        return ObsidianExportResponse(
            success=False,
            file_path=rel_path,
            obsidian_uri=uri,
            error="기존 파일이 존재하여 건너뛰었습니다 (skip 정책)",
        )

    logger.info(
        "Obsidian 노트 생성 완료",
        meeting_id=meeting_id,
        file_path=str(file_path),
    )

    return ObsidianExportResponse(
        success=True,
        file_path=rel_path,
        obsidian_uri=uri,
    )


def _has_traversal(value: str) -> bool:
    return ".." in value


def _vault_resolved(vault_path: str):
    from pathlib import Path

    return Path(vault_path).expanduser().resolve()


def _owner_id_for_task_sync(task_id: str) -> str | None:
    try:
        from backend.db.auth_models import MeetingOwnership

        with get_sync_session() as session:
            stmt = (
                select(MeetingOwnership.owner_id)
                .where(MeetingOwnership.task_id == task_id, MeetingOwnership.team_id.is_(None))
                .order_by(MeetingOwnership.created_at.asc())
                .limit(1)
            )
            owner_id = session.execute(stmt).scalar_one_or_none()
            return str(owner_id) if owner_id is not None else None
    except Exception as exc:  # pragma: no cover
        logger.warning("Obsidian owner lookup 실패", task_id=task_id, error=str(exc))
        return None


def auto_export_if_enabled_sync(meeting_id: str, redis_client=None) -> None:
    """Celery worker용 동기 자동 export 단일 진입점."""
    try:
        from backend.services.obsidian_service import obsidian_service as service

        if redis_client is None:
            from backend.workers.redis_client import get_worker_redis

            redis_client = get_worker_redis()

        owner_id = _owner_id_for_task_sync(meeting_id)
        cfg = _get_config_from_db(user_id=owner_id)
        if cfg is None or not cfg.auto_export or not cfg.vault_path:
            return

        validation = service.validate_vault(cfg.vault_path)
        if not validation["valid"]:
            logger.warning("자동 export 건너뜀: vault 경로 무효", vault=cfg.vault_path)
            return

        minutes_data = _safe_json_load(redis_client.get(f"task:min:result:{meeting_id}"))
        if not minutes_data or minutes_data.get("status") != "completed":
            logger.info("자동 export 건너뜀: minutes 미완료", meeting_id=meeting_id)
            return

        summary_data = _find_latest_summary_sync(redis_client, meeting_id)
        if not summary_data:
            logger.info("자동 export 건너뜀: 데이터 미완료", meeting_id=meeting_id)
            return

        dia_task_id = minutes_data.get("diarization_task_id")
        sentiment_data = None
        tone_data = None
        if dia_task_id:
            sentiment_data = _safe_json_load(redis_client.get(f"task:sentiment:result:{dia_task_id}"))
            if sentiment_data and sentiment_data.get("status") != "completed":
                sentiment_data = None
            tone_data = _safe_json_load(redis_client.get(f"task:tone:result:{dia_task_id}"))
            if tone_data and tone_data.get("status") != "completed":
                tone_data = None
        if sentiment_data is None:
            sentiment_data = _find_latest_completed_by_minutes_sync(
                redis_client,
                "task:sentiment:result:*",
                meeting_id,
                index_key=f"task:sentiment:by_minutes:{meeting_id}",
                result_key_prefix="task:sentiment:result:",
            )

        study_pack_data = _find_latest_study_pack_sync(redis_client, meeting_id)
        mind_map_data = _find_mind_map_sync(redis_client, summary_data)
        sales_brief_data = _safe_json_load(redis_client.get(f"sales_contact_brief:{meeting_id}"))

        meeting_data = {
            "meeting_id": meeting_id,
            "title": f"회의록 {minutes_data.get('created_at', '')[:10]}",
            "created_at": minutes_data.get("created_at", ""),
            "duration": minutes_data.get("total_duration"),
        }

        file_path = service.compute_file_path(
            cfg.vault_path,
            cfg.folder_pattern,
            cfg.filename_pattern,
            meeting_data,
        )
        note_content = service.compose_note(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            study_pack_data=study_pack_data,
            mind_map_data=mind_map_data,
            sales_brief_data=sales_brief_data,
            frontmatter_custom=cfg.frontmatter_custom,
        )
        written = service.atomic_write(
            file_path,
            note_content,
            exist_ok=(cfg.conflict_policy != "skip"),
        )
        if not written:
            logger.info("자동 export 건너뜀: 기존 파일 존재 (skip)", path=str(file_path))
            return
        logger.info("자동 export 완료", meeting_id=meeting_id, file_path=str(file_path))
    except Exception as exc:
        logger.warning("자동 export 실패 (파이프라인 영향 없음)", meeting_id=meeting_id, error=str(exc))


def _find_latest_summary_sync(redis_client, meeting_id: str) -> dict[str, Any] | None:
    return _find_latest_completed_by_minutes_sync(
        redis_client,
        "task:sum:result:*",
        meeting_id,
        index_key=f"task:sum:by_minutes:{meeting_id}",
        result_key_prefix="task:sum:result:",
    )


def _find_latest_completed_by_minutes_sync(
    redis_client,
    pattern: str,
    minutes_task_id: str,
    *,
    index_key: str | None = None,
    result_key_prefix: str | None = None,
) -> dict[str, Any] | None:
    if index_key and result_key_prefix:
        task_id_raw = redis_client.get(index_key)
        if task_id_raw:
            task_id = _decode_redis_value(task_id_raw)
            data = _safe_json_load(redis_client.get(f"{result_key_prefix}{task_id}"))
            if data and data.get("status") == "completed":
                data.setdefault("task_id", task_id)
                return data
            delete = getattr(redis_client, "delete", None)
            if delete is not None:
                delete(index_key)

    candidates: list[tuple[str, dict[str, Any]]] = []
    for key in redis_client.scan_iter(match=pattern, count=100):
        data = _safe_json_load(redis_client.get(key))
        if not data or data.get("minutes_task_id") != minutes_task_id:
            continue
        if data.get("status") != "completed":
            continue
        key_str = _decode_redis_value(key)
        if ":" in key_str:
            data.setdefault("task_id", key_str.rsplit(":", 1)[-1])
        ts = data.get("completed_at") or data.get("created_at") or ""
        candidates.append((str(ts), data))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _find_latest_study_pack_sync(redis_client, meeting_id: str) -> dict[str, Any] | None:
    candidates: list[tuple[str, dict[str, Any]]] = []
    for key in redis_client.scan_iter(match=f"study_pack:{meeting_id}:*", count=100):
        data = _safe_json_load(redis_client.get(key))
        if not data:
            continue
        candidates.append((str(data.get("created_at") or ""), data))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _find_mind_map_sync(redis_client, summary_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary_data:
        return None
    summary_task_id = summary_data.get("task_id")
    if not summary_task_id:
        return None
    task_id_raw = redis_client.get(f"task:mind:by_summary:{summary_task_id}")
    if not task_id_raw:
        return None
    task_id = _decode_redis_value(task_id_raw)
    data = _safe_json_load(redis_client.get(f"task:mind:result:{task_id}"))
    if data and data.get("status") == "completed":
        return data
    return None


async def _gather_meeting_data(
    meeting_id: str,
    redis_client: aioredis.Redis,
    db: AsyncSession | None = None,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Redis에서 회의 관련 데이터를 수집.

    Redis 키 패턴 (검증 완료):
    - minutes: task:min:result:{meeting_id}
    - summary: task:sum:result:{summaryTaskId} (minutes_task_id 필드로 역추적)
    - sentiment: task:sentiment:result:{dia_task_id} 또는 minutes_task_id 매칭
    - tone: task:tone:result:{dia_task_id}
    """
    minutes_raw = await redis_client.get(f"task:min:result:{meeting_id}")
    minutes_data = _safe_json_load(minutes_raw)
    if minutes_data and minutes_data.get("status") != "completed":
        minutes_data = None
    if minutes_data is None and db is not None:
        minutes_data = await _load_task_result_from_db(
            db,
            task_id=meeting_id,
            task_type="minutes",
        )

    summary_data = await _find_summary_by_meeting(redis_client, meeting_id, db=db)

    dia_task_id = minutes_data.get("diarization_task_id") if minutes_data else None
    sentiment_data = None
    tone_data = None

    if dia_task_id:
        sent_raw = await redis_client.get(f"task:sentiment:result:{dia_task_id}")
        sentiment_data = _safe_json_load(sent_raw)
        if sentiment_data and sentiment_data.get("status") != "completed":
            sentiment_data = None

        tone_raw = await redis_client.get(f"task:tone:result:{dia_task_id}")
        tone_data = _safe_json_load(tone_raw)
        if tone_data and tone_data.get("status") != "completed":
            tone_data = None

    if sentiment_data is None:
        sentiment_data = await _find_by_minutes_task_id(
            redis_client,
            "task:sentiment:result:*",
            meeting_id,
            index_key=f"task:sentiment:by_minutes:{meeting_id}",
            result_key_prefix="task:sentiment:result:",
            db=db,
            task_type="sentiment",
        )

    meeting_data = None
    if minutes_data:
        meeting_data = {
            "meeting_id": meeting_id,
            "title": f"회의록 {minutes_data.get('created_at', '')[:10]}",
            "created_at": minutes_data.get("created_at", ""),
            "duration": minutes_data.get("total_duration"),
        }

    return meeting_data, minutes_data, summary_data, sentiment_data, tone_data


def _safe_json_load(raw: str | bytes | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    return d


async def _find_summary_by_meeting(
    redis_client: aioredis.Redis,
    meeting_id: str,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    """minutes_task_id로 summary 결과를 역추적.

    completed 상태의 summary만 반환하며, 여러 개가 있으면 가장 최신 completed_at 기준.
    """
    return await _find_by_minutes_task_id(
        redis_client,
        "task:sum:result:*",
        meeting_id,
        index_key=f"task:sum:by_minutes:{meeting_id}",
        result_key_prefix="task:sum:result:",
        db=db,
        task_type="summary",
    )


async def _find_by_minutes_task_id(
    redis_client: aioredis.Redis,
    pattern: str,
    meeting_id: str,
    *,
    index_key: str | None = None,
    result_key_prefix: str | None = None,
    db: AsyncSession | None = None,
    task_type: str | None = None,
) -> dict[str, Any] | None:
    """Redis SCAN으로 minutes_task_id 필드가 일치하는 completed 결과를 최신순으로 찾는다."""
    if index_key and result_key_prefix:
        task_id_raw = await redis_client.get(index_key)
        if task_id_raw:
            task_id = _decode_redis_value(task_id_raw)
            raw = await redis_client.get(f"{result_key_prefix}{task_id}")
            data = _safe_json_load(raw)
            if data and data.get("status") == "completed":
                data.setdefault("task_id", task_id)
                return data
            await redis_client.delete(index_key)

    candidates: list[tuple[str, dict[str, Any]]] = []
    async for key in redis_client.scan_iter(match=pattern, count=100):
        raw = await redis_client.get(key)
        d = _safe_json_load(raw)
        if not d or d.get("minutes_task_id") != meeting_id:
            continue
        if d.get("status") != "completed":
            continue
        key_str = _decode_redis_value(key)
        if ":" in key_str:
            d.setdefault("task_id", key_str.rsplit(":", 1)[-1])
        ts = d.get("completed_at") or d.get("created_at") or ""
        candidates.append((ts, d))

    if not candidates:
        if db is not None and task_type is not None:
            return await _load_latest_task_result_by_minutes_from_db(
                db,
                task_type=task_type,
                minutes_task_id=meeting_id,
            )
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _decode_redis_value(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def _load_task_result_from_db(
    db: AsyncSession,
    *,
    task_id: str,
    task_type: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(TaskResult).where(
            TaskResult.task_id == task_id,
            TaskResult.task_type == task_type,
            TaskResult.status == "completed",
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    data = dict(record.result_data or {})
    data.setdefault("task_id", record.task_id)
    return data or None


async def _load_latest_task_result_by_minutes_from_db(
    db: AsyncSession,
    *,
    task_type: str,
    minutes_task_id: str,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(TaskResult)
        .where(TaskResult.task_type == task_type, TaskResult.status == "completed")
        .order_by(TaskResult.completed_at.desc(), TaskResult.created_at.desc())
    )
    records = result.scalars()
    all_records = getattr(records, "all", None)
    iterable = all_records() if callable(all_records) else []
    if not iterable and hasattr(records, "first"):
        first_record = records.first()
        iterable = [first_record] if first_record is not None else []

    for record in iterable:
        data = record.result_data or {}
        if data.get("minutes_task_id") == minutes_task_id:
            data = dict(data)
            data.setdefault("task_id", record.task_id)
            return data
    return None


async def _find_cached_study_pack(
    redis_client: aioredis.Redis,
    meeting_id: str,
) -> dict[str, Any] | None:
    """Find the latest cached Study Pack for a minutes task."""
    candidates: list[tuple[str, dict[str, Any]]] = []
    iterator = redis_client.scan_iter(match=f"study_pack:{meeting_id}:*", count=100)
    if isawaitable(iterator):
        iterator = await iterator
    if not hasattr(iterator, "__aiter__"):
        return None

    async for key in iterator:
        raw = await redis_client.get(key)
        data = _safe_json_load(raw)
        if not data:
            continue
        ts = data.get("created_at") or ""
        candidates.append((str(ts), data))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


async def _find_cached_mind_map(
    redis_client: aioredis.Redis,
    summary_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not summary_data:
        return None
    summary_task_id = summary_data.get("task_id")
    if not summary_task_id:
        return None
    task_id_raw = await redis_client.get(f"task:mind:by_summary:{summary_task_id}")
    if not task_id_raw:
        return None
    task_id = _decode_redis_value(task_id_raw)
    raw = await redis_client.get(f"task:mind:result:{task_id}")
    data = _safe_json_load(raw)
    if data and data.get("status") == "completed":
        return data
    return None


async def _find_cached_sales_brief(
    redis_client: aioredis.Redis,
    meeting_id: str,
    *,
    db: AsyncSession | None = None,
) -> dict[str, Any] | None:
    raw = await redis_client.get(f"sales_contact_brief:{meeting_id}")
    data = _safe_json_load(raw)
    if data:
        return data
    if db is None:
        return None
    return await _load_task_result_from_db(
        db,
        task_id=f"sales-contact-brief:{meeting_id}",
        task_type="sales_contact_brief",
    )


async def auto_export_if_enabled(
    meeting_id: str,
    redis_client: aioredis.Redis,
) -> None:
    """REQ-OBS-007: 파이프라인 완료 시 자동 export (설정된 경우).

    REQ-OBS-014: 실패해도 파이프라인에 영향을 주지 않는다.
    """
    try:
        cfg = _get_config_from_db(user_id=_owner_id_for_task_sync(meeting_id))
        if cfg is None or not cfg.auto_export or not cfg.vault_path:
            return

        validation = obsidian_service.validate_vault(cfg.vault_path)
        if not validation["valid"]:
            logger.warning(
                "자동 export 건너뜀: vault 경로 무효",
                vault=cfg.vault_path,
            )
            return

        (
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
        ) = await _gather_meeting_data(meeting_id, redis_client)
        study_pack_data = await _find_cached_study_pack(redis_client, meeting_id)
        mind_map_data = await _find_cached_mind_map(redis_client, summary_data)
        sales_brief_data = await _find_cached_sales_brief(redis_client, meeting_id)

        if not meeting_data or not summary_data:
            logger.info(
                "자동 export 건너뜀: 데이터 미완료",
                meeting_id=meeting_id,
            )
            return

        file_path = obsidian_service.compute_file_path(
            cfg.vault_path,
            cfg.folder_pattern,
            cfg.filename_pattern,
            meeting_data,
        )

        note_content = obsidian_service.compose_note(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            study_pack_data=study_pack_data,
            mind_map_data=mind_map_data,
            sales_brief_data=sales_brief_data,
            frontmatter_custom=cfg.frontmatter_custom,
        )

        written = obsidian_service.atomic_write(
            file_path,
            note_content,
            exist_ok=(cfg.conflict_policy != "skip"),
        )
        if not written:
            logger.info("자동 export 건너뜀: 기존 파일 존재 (skip)", path=str(file_path))
            return
        logger.info(
            "자동 export 완료",
            meeting_id=meeting_id,
            file_path=str(file_path),
        )
    except Exception as e:
        logger.warning(
            "자동 export 실패 (파이프라인 영향 없음)",
            meeting_id=meeting_id,
            error=str(e),
        )
