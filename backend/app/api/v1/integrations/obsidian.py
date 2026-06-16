"""SPEC-OBSIDIAN-001: Obsidian 연계 API 엔드포인트."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_redis_client
from backend.app.errors import bad_request, not_found, service_unavailable
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


def _get_config_from_db() -> ObsidianConfig | None:
    """DB에서 단일 Obsidian 설정 조회 (팀/사용자 필터는 향후 확장)."""
    try:
        with get_sync_session() as session:
            from sqlalchemy import select

            stmt = select(ObsidianConfig).order_by(ObsidianConfig.updated_at.desc()).limit(1)
            return session.scalars(stmt).first()
    except Exception as e:
        logger.warning("DB에서 Obsidian 설정 조회 실패", error=str(e))
        return None


def _save_config_to_db(req: ObsidianConfigRequest, vault_name: str) -> ObsidianConfig:
    """설정 저장 (기존 있으면 업데이트, 없으면 생성)."""
    from sqlalchemy import select

    with get_sync_session() as session:
        stmt = select(ObsidianConfig).order_by(ObsidianConfig.updated_at.desc()).limit(1)
        existing = session.scalars(stmt).first()

        if existing:
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
async def get_config() -> ObsidianConfigResponse:
    """설정 조회."""
    cfg = _get_config_from_db()
    return _config_to_response(cfg)


@router.post("/config", response_model=ObsidianConfigResponse)
async def save_config(req: ObsidianConfigRequest) -> ObsidianConfigResponse:
    """REQ-OBS-012: 설정 저장 및 검증."""
    if _has_traversal(req.vault_path):
        bad_request("경로 탐색 패턴이 감지되었습니다", error_code="PATH_TRAVERSAL_DETECTED")

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

    cfg = _save_config_to_db(req, validation["vault_name"])
    logger.info("Obsidian 설정 저장", vault=validation["vault_name"])
    return _config_to_response(cfg)


@router.post("/export/{meeting_id}", response_model=ObsidianExportResponse)
async def export_meeting(
    meeting_id: str,
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> ObsidianExportResponse:
    """REQ-OBS-006: 회의 내용을 vault에 마크다운 노트로 export."""
    cfg = _get_config_from_db()
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

    meeting_data, minutes_data, summary_data, sentiment_data, tone_data = (
        await _gather_meeting_data(meeting_id, redis_client)
    )

    if not meeting_data:
        not_found(f"회의를 찾을 수 없습니다: meeting_id={meeting_id}")

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

    if file_path.exists() and cfg.conflict_policy == "skip":
        uri = obsidian_service.build_obsidian_uri(cfg.vault_path, file_path)
        return ObsidianExportResponse(
            success=True,
            file_path=str(file_path.relative_to(_vault_resolved(cfg.vault_path))),
            obsidian_uri=uri,
            error="기존 파일이 존재하여 건너뛰었습니다 (skip 정책)",
        )

    note_content = obsidian_service.compose_note(
        meeting_data,
        minutes_data,
        summary_data,
        sentiment_data,
        tone_data,
        frontmatter_custom=cfg.frontmatter_custom,
    )

    try:
        obsidian_service.atomic_write(file_path, note_content)
    except OSError as e:
        logger.error("Obsidian 노트 파일 쓰기 실패", error=str(e), path=str(file_path))
        return ObsidianExportResponse(success=False, error=f"파일 쓰기 실패: {e}")

    uri = obsidian_service.build_obsidian_uri(cfg.vault_path, file_path)
    rel_path = str(file_path.resolve().relative_to(_vault_resolved(cfg.vault_path)))

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


async def _gather_meeting_data(
    meeting_id: str,
    redis_client: aioredis.Redis,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Redis에서 회의 관련 데이터를 수집."""
    minutes_raw = await redis_client.get(f"task:min:result:{meeting_id}")
    minutes_data = json.loads(minutes_raw) if minutes_raw else None

    summary_task_id: str | None = None
    if minutes_data:
        summary_task_id = minutes_data.get("summary_task_id")

    summary_data = None
    if summary_task_id:
        sum_raw = await redis_client.get(f"task:summary:result:{summary_task_id}")
        summary_data = json.loads(sum_raw) if sum_raw else None
    if summary_data is None:
        for pattern in ("task:summary:result:*",):
            keys = await redis_client.keys(pattern)
            for key in keys:
                raw = await redis_client.get(key)
                if raw:
                    d = json.loads(raw)
                    if d.get("minutes_task_id") == meeting_id:
                        summary_data = d
                        break
            if summary_data:
                break

    dia_task_id = minutes_data.get("diarization_task_id") if minutes_data else None
    sentiment_data = None
    tone_data = None

    if dia_task_id:
        sent_raw = await redis_client.get(f"task:sentiment:result:{dia_task_id}")
        sentiment_data = json.loads(sent_raw) if sent_raw else None

        tone_raw = await redis_client.get(f"task:tone:result:{dia_task_id}")
        tone_data = json.loads(tone_raw) if tone_raw else None

    if sentiment_data is None and minutes_data:
        for key_pat in ("task:sentiment:result:*",):
            keys = await redis_client.keys(key_pat)
            for key in keys:
                raw = await redis_client.get(key)
                if raw:
                    d = json.loads(raw)
                    if d.get("minutes_task_id") == meeting_id:
                        sentiment_data = d
                        break
            if sentiment_data:
                break

    meeting_data = None
    if minutes_data:
        meeting_data = {
            "meeting_id": meeting_id,
            "title": f"회의록 {minutes_data.get('created_at', '')[:10]}",
            "created_at": minutes_data.get("created_at", ""),
            "duration": minutes_data.get("total_duration"),
        }

    return meeting_data, minutes_data, summary_data, sentiment_data, tone_data


async def auto_export_if_enabled(
    meeting_id: str,
    redis_client: aioredis.Redis,
) -> None:
    """REQ-OBS-007: 파이프라인 완료 시 자동 export (설정된 경우).

    REQ-OBS-014: 실패해도 파이프라인에 영향을 주지 않는다.
    """
    try:
        cfg = _get_config_from_db()
        if cfg is None or not cfg.auto_export or not cfg.vault_path:
            return

        validation = obsidian_service.validate_vault(cfg.vault_path)
        if not validation["valid"]:
            logger.warning(
                "자동 export 건너뜀: vault 경로 무효",
                vault=cfg.vault_path,
            )
            return

        meeting_data, minutes_data, summary_data, sentiment_data, tone_data = (
            await _gather_meeting_data(meeting_id, redis_client)
        )

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

        if file_path.exists() and cfg.conflict_policy == "skip":
            logger.info("자동 export 건너뜀: 기존 파일 존재 (skip)", path=str(file_path))
            return

        note_content = obsidian_service.compose_note(
            meeting_data,
            minutes_data,
            summary_data,
            sentiment_data,
            tone_data,
            frontmatter_custom=cfg.frontmatter_custom,
        )

        obsidian_service.atomic_write(file_path, note_content)
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
