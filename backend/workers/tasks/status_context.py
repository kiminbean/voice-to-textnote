"""Helpers for preserving in-flight task status context in Redis."""

import json
from typing import Any, cast

PRESERVED_STATUS_CONTEXT_FIELDS = (
    "created_at",
    "user_id",
    "owner_id",
    "is_guest",
    "guest_session_id",
    "stt_task_id",
    "diarization_task_id",
    "minutes_task_id",
    "summary_task_id",
    "task_type",
)


def merge_existing_status_context(existing_raw: Any, data: dict) -> dict:
    """Carry immutable ownership/context fields across worker progress updates."""
    if not existing_raw:
        return data

    try:
        existing_data = json.loads(cast(str | bytes | bytearray, existing_raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return data

    if not isinstance(existing_data, dict):
        return data

    for field in PRESERVED_STATUS_CONTEXT_FIELDS:
        if field in data:
            continue
        value = existing_data.get(field)
        if value is not None:
            data[field] = value

    return data
