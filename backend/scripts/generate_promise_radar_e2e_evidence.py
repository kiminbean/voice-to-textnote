#!/usr/bin/env python3
"""Generate Promise Radar E2E evidence from a real recorded meeting task."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    return json.loads(value)


def _redact_command_output(value: str) -> str:
    replacements = (
        (r"(serialNumber:\s*)\S+", r"\1[redacted]"),
        (r"(ecid:\s*)\S+", r"\1[redacted]"),
        (r"(udid:\s*)\S+", r"\1[redacted]"),
        (r"(tunnelIPAddress:\s*)\S+", r"\1[redacted]"),
        (r"(ANDROID_SERIAL=)\S+", r"\1[redacted]"),
        (r"\b0000[0-9A-Fa-f-]+\.coredevice\.local\b", "[redacted].coredevice.local"),
    )
    redacted = value

    for pattern, replacement in replacements:
        redacted = re.sub(pattern, replacement, redacted)
    if "List of devices attached" in redacted:
        redacted = re.sub(
            r"(?m)^([A-Za-z0-9._:-]+)(\s+device\b)",
            r"[redacted-adb]\2",
            redacted,
        )
    return redacted


def _run(command: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": _redact_command_output(result.stdout.strip()),
            "stderr": _redact_command_output(result.stderr.strip()),
        }
    except FileNotFoundError as exc:
        return {"command": command, "exit_code": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": 124,
            "stdout": _redact_command_output((exc.stdout or "").strip()),
            "stderr": _redact_command_output((exc.stderr or "timeout").strip()),
        }


def _collect_devices() -> dict[str, Any]:
    ios_list = _run(["xcrun", "devicectl", "list", "devices"])
    ios_identifier = None
    for line in ios_list.get("stdout", "").splitlines():
        if "iPhone" in line and ("available (paired)" in line or "connected" in line):
            parts = [part for part in line.split(" ") if part]
            ios_identifier = next(
                (part for part in parts if part.count("-") == 4),
                None,
            )
            break
    ios_details = (
        _run(["xcrun", "devicectl", "device", "info", "details", "--device", ios_identifier])
        if ios_identifier
        else None
    )
    android = _run(["adb", "devices", "-l"])
    android_connected = any(
        "\tdevice" in line or " device " in line
        for line in android.get("stdout", "").splitlines()[1:]
    )
    android_model = next(
        (
            match.group(1)
            for line in android.get("stdout", "").splitlines()[1:]
            if (match := re.search(r"\bmodel:([^\s]+)", line))
        ),
        None,
    )
    return {
        "ios": {
            "connected": ios_identifier is not None,
            "identifier": ios_identifier,
            "list_output": ios_list,
            "details_output": ios_details,
        },
        "android": {
            "connected": android_connected,
            "model": android_model,
            "adb_output": android,
        },
    }


def _latest_summary(
    conn: sqlite3.Connection,
    task_id: str | None,
    *,
    owner_email: str | None = None,
) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    if task_id:
        rows = conn.execute(
            "select * from task_results where task_id=? and task_type='summary'",
            (task_id,),
        ).fetchall()
    elif owner_email:
        rows = conn.execute(
            """
            select task_results.*
            from task_results
            join meeting_ownership on meeting_ownership.task_id = task_results.task_id
            join users on users.id = meeting_ownership.owner_id
            where task_results.task_type='summary'
              and task_results.status='completed'
              and users.email=?
              and users.is_active = 1
            order by task_results.created_at desc
            """,
            (owner_email,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            select task_results.*
            from task_results
            join meeting_ownership on meeting_ownership.task_id = task_results.task_id
            join users on users.id = meeting_ownership.owner_id
            where task_results.task_type='summary'
              and task_results.status='completed'
              and users.is_active = 1
            order by task_results.created_at desc
            """
        ).fetchall()
    for row in rows:
        result = _load_json(row["result_data"])
        minutes_task_id = result.get("minutes_task_id")
        if minutes_task_id:
            return {
                "task_id": row["task_id"],
                "created_at": row["created_at"],
                "result": result,
                "minutes_task_id": minutes_task_id,
            }
    raise RuntimeError("No completed summary task with minutes_task_id was found")


def _task_result(conn: sqlite3.Connection, task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    row = conn.execute("select * from task_results where task_id=?", (task_id,)).fetchone()
    if row is None:
        return None
    return {
        "task_id": row["task_id"],
        "task_type": row["task_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "input_metadata": _load_json(row["input_metadata"]),
        "result_data": _load_json(row["result_data"]),
    }


def _recording_chain(conn: sqlite3.Connection, summary: dict[str, Any]) -> dict[str, Any]:
    minutes = _task_result(conn, summary["minutes_task_id"])
    minutes_result = minutes["result_data"] if minutes else {}
    diarization = _task_result(conn, minutes_result.get("diarization_task_id"))
    diarization_result = diarization["result_data"] if diarization else {}
    transcription = _task_result(conn, diarization_result.get("stt_task_id"))
    transcription_result = transcription["result_data"] if transcription else {}
    return {
        "summary_task_id": summary["task_id"],
        "summary_created_at": summary["created_at"],
        "minutes_task_id": summary.get("minutes_task_id"),
        "diarization_task_id": minutes_result.get("diarization_task_id"),
        "stt_task_id": diarization_result.get("stt_task_id"),
        "duration_seconds": transcription_result.get("duration")
        or minutes_result.get("total_duration"),
        "stt_model": transcription_result.get("model"),
        "summary_action_item_count": len(summary["result"].get("action_items") or []),
        "minutes_segment_count": len(minutes_result.get("segments") or []),
        "diarization_speaker_count": diarization_result.get("num_speakers")
        or minutes_result.get("total_speakers"),
    }


def _owner_email_for_task(conn: sqlite3.Connection, task_id: str) -> str:
    row = conn.execute(
        """
        select users.email
        from meeting_ownership
        join users on users.id = meeting_ownership.owner_id
        where meeting_ownership.task_id = ? and users.is_active = 1
        limit 1
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Active owner email not found for task: {task_id}")
    return str(row["email"])


def _user_token(conn: sqlite3.Connection, email: str) -> dict[str, str]:
    from backend.services.auth_service import AuthService

    row = conn.execute(
        "select id, email, display_name from users where email=? and is_active=1",
        (email,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Active user not found: {email}")
    raw_user_id = str(row["id"])
    user_id = (
        f"{raw_user_id[0:8]}-{raw_user_id[8:12]}-{raw_user_id[12:16]}-"
        f"{raw_user_id[16:20]}-{raw_user_id[20:32]}"
        if "-" not in raw_user_id and len(raw_user_id) == 32
        else raw_user_id
    )
    token = AuthService().create_access_token(
        user_id,
        row["email"],
        expires_delta=timedelta(hours=1),
    )
    return {
        "user_id": user_id,
        "email": row["email"],
        "display_name": row["display_name"],
        "authorization": f"Bearer {token}",
    }


def _api(
    base_url: str,
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Authorization": token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    started = datetime.now(UTC)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "url": url,
                "duration_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
                "json": parsed,
            }
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "url": url,
            "duration_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "error": raw,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "url": url,
            "duration_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "error": str(exc),
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_user_evidence(auth: dict[str, str]) -> dict[str, str | bool]:
    email = auth.get("email", "")
    domain = email.split("@", 1)[1] if "@" in email else ""
    return {
        "authenticated": True,
        "user_id_sha256_12": hashlib.sha256(auth["user_id"].encode("utf-8")).hexdigest()[:12],
        "email_sha256_12": hashlib.sha256(email.encode("utf-8")).hexdigest()[:12],
        "email_domain": domain,
    }


def _summarize_api_check(name: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "status": result.get("status"),
        "url": result.get("url"),
        "duration_ms": result.get("duration_ms"),
    }
    body = result.get("json") if isinstance(result.get("json"), dict) else {}
    if name == "radar_load":
        entries = body.get("ledger_entries") or []
        summary.update(
            {
                "analyzed_meetings": body.get("analyzed_meetings"),
                "ledger_entry_count": len(entries),
                "current_promise_count": len(body.get("current_promises") or []),
                "semantic_enrichment_status": body.get("semantic_enrichment_status"),
                "first_ledger_entry_id": entries[0].get("id") if entries else None,
            }
        )
    elif name == "autopilot_preview":
        assessments = body.get("assessments") or []
        summary.update(
            {
                "preview_mode": body.get("preview_mode"),
                "assessed_count": body.get("assessed_count"),
                "applied_count": body.get("applied_count"),
                "suggested_statuses": sorted(
                    {
                        item.get("suggested_status")
                        for item in assessments
                        if item.get("suggested_status")
                    }
                ),
            }
        )
    elif name == "review_queue":
        summary.update(
            {
                "queue_count": body.get("queue_count"),
                "actionable_count": body.get("actionable_count"),
                "conflict_count": body.get("conflict_count"),
            }
        )
    elif name == "pre_meeting_brief":
        summary.update(
            {
                "readiness_score": body.get("readiness_score"),
                "promise_count": len(body.get("promises") or []),
                "question_count": len(body.get("questions") or []),
                "checkpoint_count": len(body.get("checkpoints") or []),
            }
        )
    elif name == "calendar_export":
        ics_content = str(body.get("ics_content") or "")
        summary.update(
            {
                "ledger_entry_id": body.get("ledger_entry_id"),
                "ics_filename": body.get("ics_filename"),
                "has_ics_content": "BEGIN:VCALENDAR" in ics_content,
                "has_promise_id": "X-VOICE-TEXTNOTE-PROMISE-ID" in ics_content,
                "has_google_calendar_url": str(body.get("google_calendar_url") or "").startswith(
                    "https://calendar.google.com/"
                ),
            }
        )
    elif name == "assignee_quality":
        items = result.get("json") if isinstance(result.get("json"), list) else []
        confidences = [
            item.get("confidence")
            for item in items
            if isinstance(item, dict) and isinstance(item.get("confidence"), int | float)
        ]
        summary.update(
            {
                "suggestion_count": len(items),
                "top_confidence": max(confidences) if confidences else None,
            }
        )
    elif name == "due_push_dispatch_contract":
        summary.update(
            {
                "considered_count": body.get("considered_count"),
                "sent_count": body.get("sent_count"),
                "failure_count": body.get("failure_count"),
            }
        )
    elif name == "command_center":
        accuracy = body.get("accuracy_report") or {}
        evaluation = accuracy.get("evaluation") or {}
        extraction = body.get("extraction_recall") or {}
        extraction_eval = extraction.get("evaluation") or {}
        memory_graph = body.get("memory_graph") or {}
        shadow_mode = body.get("shadow_mode") or {}
        evidence_permissions = body.get("evidence_permissions") or {}
        evidence_room = body.get("evidence_room") or {}
        learning_telemetry = body.get("learning_telemetry") or {}
        live_coach = body.get("live_coach") or {}
        autopilot_quarantine = body.get("autopilot_quarantine") or {}
        meeting_recipe = body.get("meeting_recipe") or {}
        team_scorecard = body.get("team_scorecard") or {}
        google_tasks_oauth = body.get("google_tasks_oauth") or {}
        summary.update(
            {
                "focus_count": len(body.get("focus_items") or []),
                "action_count": len(body.get("actions") or []),
                "accuracy_case_count": evaluation.get("case_count"),
                "accuracy_correct_count": evaluation.get("correct_count"),
                "real_meeting_case_count": accuracy.get("real_meeting_case_count"),
                "hard_negative_case_count": accuracy.get("hard_negative_case_count"),
                "public_source_count": accuracy.get("public_source_count"),
                "target_case_count": accuracy.get("target_case_count"),
                "extraction_case_count": extraction_eval.get("case_count"),
                "extraction_expected_count": extraction_eval.get("expected_count"),
                "extraction_matched_count": extraction_eval.get("matched_count"),
                "extraction_recall": extraction_eval.get("recall"),
                "extraction_real_meeting_case_count": extraction.get("real_meeting_case_count"),
                "memory_graph_node_count": memory_graph.get("node_count"),
                "memory_graph_edge_count": memory_graph.get("edge_count"),
                "memory_graph_identity_cluster_count": memory_graph.get(
                    "identity_cluster_count"
                ),
                "memory_graph_owner_alias_review_count": memory_graph.get(
                    "owner_alias_review_count"
                ),
                "shadow_candidate_count": shadow_mode.get("candidate_count"),
                "shadow_blocked_by_evidence_count": shadow_mode.get("blocked_by_evidence_count"),
                "evidence_export_allowed": evidence_permissions.get("export_allowed"),
                "evidence_blocked_export_count": evidence_permissions.get("blocked_export_count"),
                "evidence_room_share_ready_count": evidence_room.get("share_ready_count"),
                "evidence_room_blocked_count": evidence_room.get("blocked_count"),
                "learning_telemetry_event_count": learning_telemetry.get("event_count"),
                "learning_telemetry_status_segment_count": len(
                    learning_telemetry.get("status_segments") or []
                ),
                "live_coach_prompt_count": live_coach.get("prompt_count"),
                "digest_push_ready": (body.get("digest") or {}).get("push_ready"),
                "digest_sla_due_today_count": (body.get("digest") or {}).get(
                    "sla_due_today_count"
                ),
                "autopilot_quarantine_count": autopilot_quarantine.get("quarantined_count"),
                "meeting_recipe_key": meeting_recipe.get("recipe_key"),
                "team_risk_score": team_scorecard.get("risk_score"),
                "google_tasks_oauth_production_ready": google_tasks_oauth.get("production_ready"),
                "google_tasks_oauth_ux_ready": google_tasks_oauth.get("oauth_ux_ready"),
                "google_tasks_token_exchange_ready": google_tasks_oauth.get(
                    "token_exchange_ready"
                ),
                "google_tasks_pkce_required": google_tasks_oauth.get("pkce_required"),
                "google_tasks_oauth_missing_setup_count": len(
                    google_tasks_oauth.get("missing_setup") or []
                ),
            }
        )
    if not result.get("ok") and result.get("error"):
        summary["error"] = str(result["error"])[:500]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://100.69.69.119:8000/api/v1")
    parser.add_argument("--db", default=str(ROOT / "voice_to_textnote.db"))
    parser.add_argument(
        "--email",
        help="Authenticated account email. Defaults to the selected task owner from DB.",
    )
    parser.add_argument("--task-id")
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "promise-radar-e2e-evidence-2026-07-01.json"),
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    summary = _latest_summary(conn, args.task_id, owner_email=args.email)
    chain = _recording_chain(conn, summary)
    auth = _user_token(conn, args.email or _owner_email_for_task(conn, summary["task_id"]))
    devices = _collect_devices()

    token = auth.pop("authorization")
    quoted_task = parse.quote(summary["task_id"], safe="")
    checks: dict[str, Any] = {}
    checks["radar_load"] = _api(
        args.base_url,
        "GET",
        f"promise-radar/{quoted_task}?limit=5",
        token=token,
    )
    checks["autopilot_preview"] = _api(
        args.base_url,
        "POST",
        f"promise-radar/autopilot/{quoted_task}/preview?limit=5",
        token=token,
        body={},
    )
    checks["review_queue"] = _api(
        args.base_url,
        "GET",
        f"promise-radar/autopilot/{quoted_task}/review-queue?limit=5",
        token=token,
    )
    checks["pre_meeting_brief"] = _api(
        args.base_url,
        "GET",
        "promise-radar/briefing/pre-meeting?limit=5",
        token=token,
    )
    checks["command_center"] = _api(
        args.base_url,
        "GET",
        "promise-radar/command-center?limit=10&target_case_count=1000",
        token=token,
    )

    ledger_entries = (checks["radar_load"].get("json") or {}).get("ledger_entries") or []
    first_entry_id = ledger_entries[0].get("id") if ledger_entries else None
    if first_entry_id:
        quoted_entry = parse.quote(first_entry_id, safe="")
        checks["calendar_export"] = _api(
            args.base_url,
            "POST",
            f"promise-radar/ledger/{quoted_entry}/calendar/export",
            token=token,
            body={},
        )
        checks["assignee_quality"] = _api(
            args.base_url,
            "GET",
            f"promise-radar/ledger/{quoted_entry}/assignee-suggestions?limit=5",
            token=token,
        )
    else:
        checks["calendar_export"] = {"ok": False, "error": "No ledger entries returned"}
        checks["assignee_quality"] = {"ok": False, "error": "No ledger entries returned"}

    checks["due_push_dispatch_contract"] = _api(
        args.base_url,
        "POST",
        "promise-radar/ledger/notifications/due?limit=5",
        token=token,
        body={},
    )

    summarized_checks = {
        name: _summarize_api_check(name, result) for name, result in checks.items()
    }

    pass_checks = {
        "ios_device_connected": bool(devices["ios"]["connected"]),
        "android_device_connected": bool(devices["android"]["connected"]),
        "actual_recording_chain": bool(chain["duration_seconds"] and chain["minutes_task_id"]),
        "radar_load": bool(checks["radar_load"].get("ok")),
        "autopilot_preview": bool(checks["autopilot_preview"].get("ok")),
        "review_queue": bool(checks["review_queue"].get("ok")),
        "calendar_export": bool(
            summarized_checks["calendar_export"].get("ok")
            and summarized_checks["calendar_export"].get("has_ics_content")
            and summarized_checks["calendar_export"].get("has_promise_id")
        ),
        "assignee_quality": bool(checks["assignee_quality"].get("ok")),
        "pre_meeting_brief": bool(checks["pre_meeting_brief"].get("ok")),
        "due_push_dispatch_contract": bool(checks["due_push_dispatch_contract"].get("ok")),
        "command_center": bool(checks["command_center"].get("ok")),
        "command_center_accuracy_baseline": bool(
            (summarized_checks["command_center"].get("accuracy_case_count") or 0) >= 1089
            and (summarized_checks["command_center"].get("real_meeting_case_count") or 0) >= 1000
        ),
        "command_center_v15_contract": bool(
            isinstance(
                summarized_checks["command_center"].get("memory_graph_node_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("shadow_candidate_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("evidence_export_allowed"),
                bool,
            )
            and isinstance(summarized_checks["command_center"].get("team_risk_score"), int)
        ),
        "command_center_v16_contract": bool(
            (summarized_checks["command_center"].get("extraction_case_count") or 0) >= 50
            and (summarized_checks["command_center"].get("extraction_recall") or 0) >= 0.95
            and isinstance(summarized_checks["command_center"].get("action_count"), int)
            and isinstance(
                summarized_checks["command_center"].get("google_tasks_oauth_production_ready"),
                bool,
            )
        ),
        "command_center_v17_contract": bool(
            isinstance(
                summarized_checks["command_center"].get("learning_telemetry_event_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("live_coach_prompt_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("evidence_room_share_ready_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("autopilot_quarantine_count"),
                int,
            )
            and bool(summarized_checks["command_center"].get("meeting_recipe_key"))
        ),
        "command_center_v19_contract": bool(
            (summarized_checks["command_center"].get("hard_negative_case_count") or 0) >= 50
            and (summarized_checks["command_center"].get("public_source_count") or 0) >= 2
            and isinstance(
                summarized_checks["command_center"].get("memory_graph_identity_cluster_count"),
                int,
            )
            and isinstance(
                summarized_checks["command_center"].get("memory_graph_owner_alias_review_count"),
                int,
            )
            and isinstance(summarized_checks["command_center"].get("digest_push_ready"), bool)
            and summarized_checks["command_center"].get("google_tasks_pkce_required") is True
            and isinstance(
                summarized_checks["command_center"].get("google_tasks_oauth_ux_ready"),
                bool,
            )
            and isinstance(
                summarized_checks["command_center"].get("google_tasks_token_exchange_ready"),
                bool,
            )
        ),
    }

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target_base_url": args.base_url,
        "user": _safe_user_evidence(auth),
        "devices": devices,
        "actual_recording": chain,
        "checks": summarized_checks,
        "pass_checks": pass_checks,
        "overall_pass": all(pass_checks.values()),
        "android_release_device_note": (
            "Android ADB device was not connected during this evidence run."
            if not devices["android"]["connected"]
            else "Android ADB device was connected."
        ),
    }
    output = Path(args.output)
    _write_json(output, payload)
    print(json.dumps({"output": str(output), "overall_pass": payload["overall_pass"]}, indent=2))
    return 0 if payload["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
