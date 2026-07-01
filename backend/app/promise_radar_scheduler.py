"""Background scheduler for Promise Radar due notifications."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime

from backend.app.dependencies import _session_factory
from backend.services.promise_radar_service import PromiseRadarService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def promise_radar_scheduler_enabled() -> bool:
    """Return whether the due-notification scheduler should run in this process."""
    return os.environ.get("PROMISE_RADAR_NOTIFICATION_SCHEDULER_ENABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        logger.warning("Invalid Promise Radar scheduler integer env", name=name)
        return default


async def run_promise_radar_notification_tick(limit: int = 100) -> None:
    """Dispatch due Promise Radar notifications once across all scoped ledger entries."""
    service = PromiseRadarService()
    async with _session_factory() as session:
        result = await service.dispatch_due_notifications(
            session,
            now=datetime.now(UTC),
            limit=limit,
            allow_global=True,
        )
    logger.info(
        "Promise Radar due notification tick complete",
        considered=result.considered_count,
        sent=result.sent_count,
        failures=result.failure_count,
    )


async def _promise_radar_notification_loop(interval_seconds: int, limit: int) -> None:
    while True:
        try:
            await run_promise_radar_notification_tick(limit=limit)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Promise Radar due notification tick failed", error=str(exc))
        await asyncio.sleep(interval_seconds)


def start_promise_radar_notification_scheduler() -> asyncio.Task | None:
    """Start the scheduler task when explicitly enabled."""
    if not promise_radar_scheduler_enabled() or os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    interval = _env_int("PROMISE_RADAR_NOTIFICATION_SCHEDULER_INTERVAL_SECONDS", 300)
    limit = _env_int("PROMISE_RADAR_NOTIFICATION_SCHEDULER_LIMIT", 100)
    task = asyncio.create_task(
        _promise_radar_notification_loop(
            interval_seconds=max(30, interval),
            limit=max(1, min(limit, 500)),
        ),
        name="promise-radar-notification-scheduler",
    )
    logger.info("Promise Radar due notification scheduler started", interval_seconds=interval)
    return task


async def stop_promise_radar_notification_scheduler(task: asyncio.Task | None) -> None:
    """Cancel and await a scheduler task created by start_promise_radar_notification_scheduler."""
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    logger.info("Promise Radar due notification scheduler stopped")
