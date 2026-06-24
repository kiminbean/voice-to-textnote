"""Obsidian API helper and endpoint behavior coverage."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.api.v1.integrations import obsidian
from backend.app.exceptions import VoiceNoteError
from backend.db.models import TaskResult
from backend.schemas.obsidian import ObsidianConfigRequest, ObsidianValidateRequest


def _cfg(**overrides):
    defaults = {
        "vault_path": "/vault",
        "vault_name": "vault",
        "folder_pattern": "Meetings/{{date}}",
        "filename_pattern": "{{title}}",
        "auto_export": False,
        "conflict_policy": "overwrite",
        "frontmatter_custom": {"additional_tags": ["ai"]},
        "note_template_id": None,
    }
    defaults.update(overrides)
    cfg = MagicMock()
    for key, value in defaults.items():
        setattr(cfg, key, value)
    return cfg


def _valid_vault(name: str = "vault") -> dict:
    return {
        "valid": True,
        "vault_name": name,
        "obsidian_folder_exists": True,
        "writable": True,
        "is_symlink": False,
    }


def _completed_minutes() -> dict:
    return {
        "status": "completed",
        "created_at": "2026-06-20T01:02:03Z",
        "total_duration": 120,
        "diarization_task_id": "dia-1",
        "segments": [{"speaker_name": "Alice", "text": "hello", "start": 0}],
    }


def _redis_with(values: dict[str, object], scan_keys: list[str] | None = None):
    redis = MagicMock()

    async def get(key):
        value = values.get(key)
        if isinstance(value, dict | list):
            return json.dumps(value)
        return value

    async def scan_iter(match=None, count=None):
        del count
        for key in scan_keys or []:
            if (
                match is None
                or Path(key).match(match.replace("*", "**"))
                or key.startswith(match.rstrip("*"))
            ):
                yield key

    redis.get = AsyncMock(side_effect=get)
    redis.delete = AsyncMock()
    redis.scan_iter = MagicMock(side_effect=scan_iter)
    return redis


class _SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def _session_with_existing(existing):
    session = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = existing
    session.scalars.return_value = scalars
    return session


class _AsyncScalarResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        values = self.value if isinstance(self.value, list) else [self.value]
        return _AsyncScalars(values)


class _AsyncScalars:
    def __init__(self, values):
        self.values = [value for value in values if value is not None]

    def first(self):
        return self.values[0] if self.values else None


class _FakeAsyncSession:
    def __init__(self, *values):
        self.values = list(values)
        self.executed = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        value = self.values.pop(0) if self.values else None
        return _AsyncScalarResult(value)


def test_get_config_from_db_returns_latest_or_none_on_error(monkeypatch):
    cfg = _cfg()
    session = _session_with_existing(cfg)
    monkeypatch.setattr(obsidian, "get_sync_session", lambda: _SessionContext(session))

    assert obsidian._get_config_from_db() is cfg
    session.scalars.assert_called_once()

    monkeypatch.setattr(
        obsidian,
        "get_sync_session",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    assert obsidian._get_config_from_db() is None


def test_get_config_from_db_scopes_by_user(monkeypatch):
    cfg = _cfg(user_id="user-1")
    session = _session_with_existing(cfg)
    monkeypatch.setattr(obsidian, "get_sync_session", lambda: _SessionContext(session))

    assert obsidian._get_config_from_db(user_id="user-1") is cfg

    rendered = str(session.scalars.call_args.args[0])
    assert "obsidian_configs.user_id" in rendered


def test_save_config_to_db_updates_existing_config(monkeypatch):
    existing = _cfg(vault_path="/old", vault_name="Old")
    session = _session_with_existing(existing)
    monkeypatch.setattr(obsidian, "get_sync_session", lambda: _SessionContext(session))

    result = obsidian._save_config_to_db(
        ObsidianConfigRequest(
            vault_path="/new",
            folder_pattern="Folder/{{date}}",
            filename_pattern="{{title}}.md",
            auto_export=True,
            conflict_policy="skip",
            frontmatter_custom={"team": "platform"},
            note_template_id="template-1",
        ),
        "NewVault",
        user_id="user-1",
    )

    assert result is existing
    assert existing.vault_path == "/new"
    assert existing.vault_name == "NewVault"
    assert existing.auto_export is True
    assert existing.conflict_policy == "skip"
    assert existing.user_id == "user-1"
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(existing)
    session.add.assert_not_called()


def test_save_config_to_db_creates_new_config(monkeypatch):
    session = _session_with_existing(None)
    monkeypatch.setattr(obsidian, "get_sync_session", lambda: _SessionContext(session))

    result = obsidian._save_config_to_db(
        ObsidianConfigRequest(vault_path="/vault"),
        "Vault",
        user_id="user-1",
    )

    assert result.vault_path == "/vault"
    assert result.vault_name == "Vault"
    assert result.user_id == "user-1"
    session.add.assert_called_once_with(result)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(result)


def test_config_to_response_returns_defaults_when_missing():
    response = obsidian._config_to_response(None)

    assert response.vault_path == ""
    assert response.vault_valid is False
    assert response.conflict_policy == "overwrite"


def test_config_to_response_validates_saved_config(monkeypatch):
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())

    response = obsidian._config_to_response(_cfg())

    assert response.vault_valid is True
    assert response.frontmatter_custom == {"additional_tags": ["ai"]}


@pytest.mark.asyncio
async def test_get_config_reads_saved_config(monkeypatch):
    monkeypatch.setattr(
        obsidian,
        "_get_config_from_db",
        lambda **kwargs: _cfg(vault_name="SavedVault"),
    )
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())

    response = await obsidian.get_config()

    assert response.vault_name == "SavedVault"
    assert response.vault_valid is True


@pytest.mark.asyncio
async def test_validate_vault_returns_service_result(monkeypatch):
    monkeypatch.setattr(
        obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault("Work")
    )

    response = await obsidian.validate_vault(ObsidianValidateRequest(vault_path="/vault"))

    assert response.valid is True
    assert response.vault_name == "Work"


@pytest.mark.asyncio
async def test_save_config_rejects_traversal_patterns():
    req = ObsidianConfigRequest(vault_path="/vault", folder_pattern="../escape")

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.save_config(req)

    assert exc.value.status_code == 400
    assert exc.value.error_code == "PATH_TRAVERSAL_DETECTED"


@pytest.mark.asyncio
async def test_save_config_rejects_invalid_symlink_vault(monkeypatch):
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "validate_vault",
        lambda path: {**_valid_vault(), "valid": False, "is_symlink": True},
    )
    req = ObsidianConfigRequest(vault_path="/vault")

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.save_config(req)

    assert exc.value.error_code == "SYMLINK_VAULT_DETECTED"


@pytest.mark.asyncio
async def test_save_config_rejects_invalid_non_symlink_vault_and_bad_policy(monkeypatch):
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "validate_vault",
        lambda path: {**_valid_vault(), "valid": False, "is_symlink": False},
    )

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.save_config(ObsidianConfigRequest(vault_path="/vault"))
    assert exc.value.error_code == "INVALID_VAULT_PATH"

    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.save_config(
            ObsidianConfigRequest(vault_path="/vault", conflict_policy="merge")
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_save_config_rejects_vault_and_filename_traversal():
    for kwargs in [
        {"vault_path": "../vault"},
        {"vault_path": "/vault", "filename_pattern": "../note"},
    ]:
        with pytest.raises(VoiceNoteError) as exc:
            await obsidian.save_config(ObsidianConfigRequest(**kwargs))
        assert exc.value.error_code == "PATH_TRAVERSAL_DETECTED"


@pytest.mark.asyncio
async def test_save_config_persists_valid_config(monkeypatch):
    monkeypatch.setattr(
        obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault("TeamVault")
    )
    saved = _cfg(vault_name="TeamVault")
    monkeypatch.setattr(obsidian, "_save_config_to_db", lambda req, vault_name, **kwargs: saved)

    response = await obsidian.save_config(
        ObsidianConfigRequest(vault_path="/vault", conflict_policy="skip")
    )

    assert response.vault_name == "TeamVault"
    assert response.vault_valid is True


@pytest.mark.asyncio
async def test_export_meeting_uses_scoped_config_and_task_access(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path), user_id="user-1")
    target = tmp_path / "n.md"
    request = MagicMock()
    request.state.user_id = "user-1"
    current_user = MagicMock(id="user-1")
    db = _FakeAsyncSession()
    require_access = AsyncMock()
    monkeypatch.setattr(obsidian, "_get_config_from_db", MagicMock(return_value=cfg))
    monkeypatch.setattr(obsidian, "require_task_access", require_access)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(obsidian.obsidian_service, "compute_file_path", lambda *args: target)
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", lambda *args, **kwargs: "note")
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        obsidian.obsidian_service, "build_obsidian_uri", lambda *args: "obsidian://open"
    )

    response = await obsidian.export_meeting(
        "meeting-1",
        _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
        request=request,
        db=db,
        current_user=current_user,
    )

    assert response.success is True
    obsidian._get_config_from_db.assert_called_once_with(user_id="user-1")
    require_access.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_meeting_requires_config(monkeypatch):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: None)

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.export_meeting("meeting-1", AsyncMock())

    assert exc.value.error_code == "OBSIDIAN_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_export_meeting_returns_not_found_without_minutes(monkeypatch):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: _cfg())
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.export_meeting("missing", _redis_with({}))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_export_meeting_rejects_invalid_vault(monkeypatch):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: _cfg())
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "validate_vault",
        lambda path: {**_valid_vault(), "valid": False},
    )

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.export_meeting("meeting-1", AsyncMock())

    assert exc.value.error_code == "OBSIDIAN_VAULT_INVALID"


@pytest.mark.asyncio
async def test_export_meeting_translates_path_traversal(monkeypatch):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: _cfg())
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "compute_file_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("경로 탐색 패턴")),
    )

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.export_meeting(
            "meeting-1",
            _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
        )

    assert exc.value.error_code == "PATH_TRAVERSAL_DETECTED"


@pytest.mark.asyncio
async def test_export_meeting_translates_generic_compute_path_error(monkeypatch):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: _cfg())
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "compute_file_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad pattern")),
    )

    with pytest.raises(VoiceNoteError) as exc:
        await obsidian.export_meeting(
            "meeting-1",
            _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
        )

    assert exc.value.status_code == 400
    assert exc.value.error_code != "PATH_TRAVERSAL_DETECTED"


@pytest.mark.asyncio
async def test_export_meeting_returns_write_error(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path))
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(
        obsidian.obsidian_service, "compute_file_path", lambda *args: tmp_path / "n.md"
    )
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", lambda *args, **kwargs: "note")
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "atomic_write",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )

    response = await obsidian.export_meeting(
        "meeting-1",
        _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
    )

    assert response.success is False
    assert "disk full" in response.error


@pytest.mark.asyncio
async def test_export_meeting_reports_skip_policy(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path), conflict_policy="skip")
    target = tmp_path / "n.md"
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(obsidian.obsidian_service, "compute_file_path", lambda *args: target)
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", lambda *args, **kwargs: "note")
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        obsidian.obsidian_service, "build_obsidian_uri", lambda *args: "obsidian://open"
    )

    response = await obsidian.export_meeting(
        "meeting-1",
        _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
    )

    assert response.success is False
    assert response.file_path == "n.md"
    assert "skip 정책" in response.error


@pytest.mark.asyncio
async def test_export_meeting_success(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path))
    target = tmp_path / "n.md"
    compose = MagicMock(return_value="note")
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(obsidian.obsidian_service, "compute_file_path", lambda *args: target)
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", compose)
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        obsidian.obsidian_service, "build_obsidian_uri", lambda *args: "obsidian://open"
    )

    response = await obsidian.export_meeting(
        "meeting-1",
        _redis_with({"task:min:result:meeting-1": _completed_minutes()}),
    )

    assert response.success is True
    assert response.file_path == "n.md"
    assert response.obsidian_uri == "obsidian://open"
    assert compose.call_args.kwargs["study_pack_data"] is None


@pytest.mark.asyncio
async def test_export_meeting_passes_cached_study_pack_to_note(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path))
    target = tmp_path / "n.md"
    compose = MagicMock(return_value="note")
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(obsidian.obsidian_service, "compute_file_path", lambda *args: target)
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", compose)
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        obsidian.obsidian_service, "build_obsidian_uri", lambda *args: "obsidian://open"
    )

    await obsidian.export_meeting(
        "meeting-1",
        _redis_with(
            {
                "task:min:result:meeting-1": _completed_minutes(),
                "study_pack:meeting-1:lecture": {
                    "mode": "lecture",
                    "study_notes": "학습 노트",
                    "created_at": "2026-06-21T00:00:00Z",
                },
            },
            scan_keys=["study_pack:meeting-1:lecture"],
        ),
    )

    assert compose.call_args.kwargs["study_pack_data"]["study_notes"] == "학습 노트"


@pytest.mark.asyncio
async def test_export_meeting_passes_mind_map_and_sales_brief_to_note(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path))
    compose = MagicMock(return_value="note")
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(
        obsidian.obsidian_service, "compute_file_path", lambda *args: tmp_path / "n.md"
    )
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", compose)
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        obsidian.obsidian_service, "build_obsidian_uri", lambda *args: "obsidian://open"
    )

    await obsidian.export_meeting(
        "meeting-1",
        _redis_with(
            {
                "task:min:result:meeting-1": _completed_minutes(),
                "task:sum:by_minutes:meeting-1": "sum-1",
                "task:sum:result:sum-1": {
                    "task_id": "sum-1",
                    "status": "completed",
                    "minutes_task_id": "meeting-1",
                },
                "task:mind:by_summary:sum-1": "mind-1",
                "task:mind:result:mind-1": {
                    "status": "completed",
                    "root": {"title": "핵심 관계", "children": []},
                    "edges": [],
                },
                "sales_contact_brief:meeting-1": {
                    "next_steps": ["고객에게 견적 발송"],
                    "follow_up_message": "후속 메일 초안",
                    "created_at": "2026-06-24T00:00:00Z",
                },
            }
        ),
    )

    assert compose.call_args.kwargs["mind_map_data"]["root"]["title"] == "핵심 관계"
    assert compose.call_args.kwargs["sales_brief_data"]["next_steps"] == ["고객에게 견적 발송"]


@pytest.mark.asyncio
async def test_gather_meeting_data_falls_back_to_db_when_redis_minutes_missing():
    record = TaskResult(
        task_id="meeting-1",
        task_type="minutes",
        status="completed",
        result_data=_completed_minutes(),
    )

    meeting, minutes, summary, sentiment, tone = await obsidian._gather_meeting_data(
        "meeting-1",
        _redis_with({}),
        db=_FakeAsyncSession(record),
    )

    assert meeting["meeting_id"] == "meeting-1"
    assert minutes["status"] == "completed"
    assert summary is None
    assert sentiment is None
    assert tone is None


@pytest.mark.asyncio
async def test_find_summary_uses_source_index_before_scan():
    redis = _redis_with(
        {
            "task:sum:by_minutes:meeting-1": "sum-indexed",
            "task:sum:result:sum-indexed": {
                "status": "completed",
                "minutes_task_id": "meeting-1",
                "completed_at": "2026-06-24T00:00:00Z",
            },
        },
        scan_keys=["task:sum:result:old"],
    )

    result = await obsidian._find_summary_by_meeting(redis, "meeting-1")

    assert result["completed_at"] == "2026-06-24T00:00:00Z"
    redis.scan_iter.assert_not_called()


@pytest.mark.asyncio
async def test_gather_meeting_data_filters_incomplete_and_uses_latest_summary():
    redis = _redis_with(
        {
            "task:min:result:meeting-1": _completed_minutes(),
            "task:sum:result:old": {
                "status": "completed",
                "minutes_task_id": "meeting-1",
                "completed_at": "2026-01-01T00:00:00Z",
            },
            "task:sum:result:new": {
                "status": "completed",
                "minutes_task_id": "meeting-1",
                "completed_at": "2026-06-20T00:00:00Z",
            },
            "task:sentiment:result:dia-1": {"status": "failed"},
            "task:tone:result:dia-1": {"status": "completed", "overall_tone": "calm"},
            "task:sentiment:result:fallback": {
                "status": "completed",
                "minutes_task_id": "meeting-1",
                "completed_at": "2026-06-20T00:00:00Z",
            },
        },
        scan_keys=[
            "task:sum:result:old",
            "task:sum:result:new",
            "task:sentiment:result:fallback",
        ],
    )

    meeting, minutes, summary, sentiment, tone = await obsidian._gather_meeting_data(
        "meeting-1", redis
    )

    assert meeting["meeting_id"] == "meeting-1"
    assert minutes["status"] == "completed"
    assert summary["completed_at"] == "2026-06-20T00:00:00Z"
    assert sentiment["status"] == "completed"
    assert tone["overall_tone"] == "calm"


@pytest.mark.asyncio
async def test_gather_meeting_data_drops_incomplete_minutes_and_tone():
    meeting, minutes, summary, sentiment, tone = await obsidian._gather_meeting_data(
        "meeting-1",
        _redis_with(
            {
                "task:min:result:meeting-1": {"status": "failed"},
                "task:sum:result:summary": {
                    "status": "completed",
                    "minutes_task_id": "meeting-1",
                    "created_at": "2026-06-20T00:00:00Z",
                },
                "task:sentiment:result:fallback": {
                    "status": "completed",
                    "minutes_task_id": "meeting-1",
                },
            },
            scan_keys=["task:sum:result:summary", "task:sentiment:result:fallback"],
        ),
    )

    assert meeting is None
    assert minutes is None
    assert summary["status"] == "completed"
    assert sentiment["status"] == "completed"
    assert tone is None


@pytest.mark.asyncio
async def test_gather_meeting_data_drops_incomplete_tone_for_completed_minutes():
    meeting, minutes, summary, sentiment, tone = await obsidian._gather_meeting_data(
        "meeting-1",
        _redis_with(
            {
                "task:min:result:meeting-1": _completed_minutes(),
                "task:tone:result:dia-1": {"status": "failed"},
            }
        ),
    )

    assert meeting["meeting_id"] == "meeting-1"
    assert minutes["status"] == "completed"
    assert summary is None
    assert sentiment is None
    assert tone is None


def test_safe_json_load_rejects_invalid_payloads():
    assert obsidian._safe_json_load(None) is None
    assert obsidian._safe_json_load("{bad") is None
    assert obsidian._safe_json_load("[1, 2]") is None


@pytest.mark.asyncio
async def test_find_by_minutes_task_id_skips_invalid_and_incomplete_entries():
    redis = _redis_with(
        {
            "task:any:bad-json": "{bad",
            "task:any:other-meeting": {"status": "completed", "minutes_task_id": "other"},
            "task:any:failed": {"status": "failed", "minutes_task_id": "meeting-1"},
        },
        scan_keys=["task:any:bad-json", "task:any:other-meeting", "task:any:failed"],
    )

    assert await obsidian._find_by_minutes_task_id(redis, "task:any:*", "meeting-1") is None


@pytest.mark.asyncio
async def test_find_cached_study_pack_uses_latest_created_at():
    redis = _redis_with(
        {
            "study_pack:meeting-1:lecture": {
                "mode": "lecture",
                "study_notes": "오래된 노트",
                "created_at": "2026-01-01T00:00:00Z",
            },
            "study_pack:meeting-1:interview": {
                "mode": "interview",
                "study_notes": "최신 노트",
                "created_at": "2026-06-21T00:00:00Z",
            },
            "study_pack:meeting-1:bad": "{bad",
        },
        scan_keys=[
            "study_pack:meeting-1:lecture",
            "study_pack:meeting-1:interview",
            "study_pack:meeting-1:bad",
        ],
    )

    result = await obsidian._find_cached_study_pack(redis, "meeting-1")

    assert result["mode"] == "interview"
    assert result["study_notes"] == "최신 노트"


@pytest.mark.asyncio
async def test_find_cached_study_pack_returns_none_when_scan_iter_is_not_async_iterable():
    redis = AsyncMock()
    redis.scan_iter.return_value = []

    assert await obsidian._find_cached_study_pack(redis, "meeting-1") is None


@pytest.mark.asyncio
async def test_auto_export_if_enabled_isolated_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: _cfg(auto_export=False))
    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())

    cfg = _cfg(vault_path=str(tmp_path), auto_export=True)
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(
        obsidian, "_gather_meeting_data", AsyncMock(return_value=(None, None, None, None, None))
    )
    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())


@pytest.mark.asyncio
async def test_auto_export_if_enabled_skips_invalid_vault_and_writes_success(monkeypatch, tmp_path):
    cfg = _cfg(vault_path=str(tmp_path), auto_export=True)
    monkeypatch.setattr(obsidian, "_get_config_from_db", lambda **kwargs: cfg)
    monkeypatch.setattr(
        obsidian.obsidian_service,
        "validate_vault",
        lambda path: {**_valid_vault(), "valid": False},
    )
    gather = AsyncMock(return_value=({"title": "x"}, {}, {"summary_text": "done"}, None, None))
    monkeypatch.setattr(obsidian, "_gather_meeting_data", gather)

    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())
    gather.assert_not_awaited()

    monkeypatch.setattr(obsidian.obsidian_service, "validate_vault", lambda path: _valid_vault())
    monkeypatch.setattr(obsidian, "_gather_meeting_data", gather)
    monkeypatch.setattr(
        obsidian.obsidian_service, "compute_file_path", lambda *args: tmp_path / "n.md"
    )
    compose = MagicMock(return_value="note")
    atomic_write = MagicMock(return_value=True)
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", compose)
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", atomic_write)

    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())

    gather.assert_awaited_once()
    compose.assert_called_once()
    atomic_write.assert_called_once_with(tmp_path / "n.md", "note", exist_ok=True)

    monkeypatch.setattr(
        obsidian,
        "_gather_meeting_data",
        AsyncMock(return_value=({"title": "x"}, {}, {"summary_text": "done"}, None, None)),
    )
    monkeypatch.setattr(
        obsidian.obsidian_service, "compute_file_path", lambda *args: tmp_path / "n.md"
    )
    monkeypatch.setattr(obsidian.obsidian_service, "compose_note", lambda *args, **kwargs: "note")
    monkeypatch.setattr(obsidian.obsidian_service, "atomic_write", lambda *args, **kwargs: False)
    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())

    monkeypatch.setattr(
        obsidian.obsidian_service,
        "compute_file_path",
        lambda *args: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    await obsidian.auto_export_if_enabled("meeting-1", AsyncMock())
