import json
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.schemas.advanced_search import AdvancedSearchRequest, SearchFilter
from backend.services.advanced_search import AdvancedSearchService


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.store[key] = value

    async def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        self.lists[key] = self.lists.get(key, [])[start : end + 1]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        return self.lists.get(key, [])[start : end + 1]

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def lrem(self, key: str, _count: int, value: str) -> None:
        self.lists[key] = [item for item in self.lists.get(key, []) if item != value]


@pytest.mark.asyncio
async def test_search_history_uses_json_storage() -> None:
    redis = FakeRedis()
    service = AdvancedSearchService()
    await service.initialize(redis)  # type: ignore[arg-type]
    request = AdvancedSearchRequest(
        query="회의록",
        filters=SearchFilter(start_date=datetime(2026, 1, 1, tzinfo=UTC)),
    )

    await service._save_search_history(request, search_time_ms=12.5)
    history = await service.get_search_history()

    assert history[0]["query"] == "회의록"
    assert history[0]["filters"]["start_date"] == "2026-01-01T00:00:00Z"
    stored_payload = next(iter(redis.store.values()))
    assert json.loads(stored_payload)["query"] == "회의록"


@pytest.mark.asyncio
async def test_get_search_history_ignores_non_json_without_eval(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    redis.lists["search_history:recent"] = ["malicious", "valid"]
    redis.store["search_history:malicious"] = "__import__('os').system('echo exploited')"
    redis.store["search_history:valid"] = json.dumps({"id": "valid", "query": "safe"})
    service = AdvancedSearchService()
    await service.initialize(redis)  # type: ignore[arg-type]

    def fail_if_eval_runs(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("eval must not be used for search history")

    monkeypatch.setattr("builtins.eval", fail_if_eval_runs)

    assert await service.get_search_history() == [{"id": "valid", "query": "safe"}]


@pytest.mark.asyncio
async def test_saved_searches_are_loaded_from_redis() -> None:
    redis = FakeRedis()
    redis.lists["saved_search:recent"] = ["saved_1"]
    redis.store["saved_search:saved_1"] = json.dumps(
        {
            "id": "saved_1",
            "name": "저장 검색",
            "query": "회의록",
            "filters": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_used_at": "2026-01-02T00:00:00+00:00",
            "usage_count": 1,
        }
    )
    service = AdvancedSearchService()
    await service.initialize(redis)  # type: ignore[arg-type]

    assert await service.get_saved_searches() == [json.loads(redis.store["saved_search:saved_1"])]


@pytest.mark.asyncio
async def test_save_search_promotes_existing_history_to_json_saved_search() -> None:
    redis = FakeRedis()
    redis.store["search_history:hist_1"] = json.dumps(
        {
            "id": "hist_1",
            "query": "프로젝트",
            "filters": {"content_types": ["minutes"]},
            "result_count": 3,
            "search_time_ms": 14.2,
            "created_at": "2026-01-01T00:00:00+00:00",
            "is_saved": False,
        }
    )
    service = AdvancedSearchService()
    await service.initialize(redis)  # type: ignore[arg-type]

    saved = await service.save_search("hist_1", "프로젝트 검색")

    assert saved is not None
    assert saved["name"] == "프로젝트 검색"
    assert saved["query"] == "프로젝트"
    assert redis.lists["saved_search:recent"] == [saved["id"]]
    assert json.loads(redis.store["search_history:hist_1"])["is_saved"] is True


@pytest.mark.asyncio
async def test_delete_search_history_removes_key_and_recent_id() -> None:
    redis = FakeRedis()
    redis.store["search_history:hist_1"] = json.dumps({"id": "hist_1", "query": "회의록"})
    redis.lists["search_history:recent"] = ["hist_2", "hist_1", "hist_1"]
    service = AdvancedSearchService()
    await service.initialize(redis)  # type: ignore[arg-type]

    await service.delete_search_history("hist_1")

    assert "search_history:hist_1" not in redis.store
    assert redis.lists["search_history:recent"] == ["hist_2"]
