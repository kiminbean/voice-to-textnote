"""Small compatibility helpers for service-layer database sessions."""

import inspect
from typing import Any


async def add_to_session(session: Any, instance: Any) -> None:
    """Add an instance and consume awaitable test doubles without changing SQLAlchemy behavior."""
    result = session.add(instance)
    if inspect.isawaitable(result):
        await result
