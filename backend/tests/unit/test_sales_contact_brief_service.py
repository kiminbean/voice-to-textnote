import json
from unittest.mock import MagicMock

import pytest

from backend.services.sales_contact_brief_service import (
    SalesContactBriefService,
    SalesContactBriefSourceNotFoundError,
    SalesContactBriefValidationError,
    _parse_created_at,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        self.set_calls.append((key, value, ex))


class FakeSyncSession:
    def connection(self):
        return object()


class FakeDbSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def run_sync(self, fn):
        return fn(FakeSyncSession())

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def make_minutes_payload() -> dict:
    return {
        "task_id": "min-sales-001",
        "raw_text": "Acme CTO 김민수님은 보안 감사 자동화가 필요하고 다음 주 화요일 데모를 원합니다.",
        "segments": [
            {
                "speaker_name": "영업",
                "start": 0.0,
                "end": 8.0,
                "text": "Acme CTO 김민수님은 보안 감사 자동화가 필요하다고 했습니다.",
            },
            {
                "speaker_name": "고객",
                "start": 9.0,
                "end": 16.0,
                "text": "다음 주 화요일에 데모를 보고 견적을 받고 싶습니다.",
            },
        ],
    }


def make_ai_payload() -> dict:
    return {
        "contact": {
            "name": "김민수",
            "company": "Acme",
            "role": "CTO",
            "email": None,
            "phone": None,
        },
        "deal": {
            "stage": "demo_requested",
            "value_hint": None,
            "urgency": "high",
        },
        "customer_needs": ["보안 감사 자동화", "데모 확인"],
        "pain_points": ["수동 감사 시간이 오래 걸림"],
        "objections": ["견적 확인 필요"],
        "next_steps": [
            {"task": "다음 주 화요일 데모 일정 확정", "owner": "영업", "due": "다음 주 화요일"}
        ],
        "follow_up_message": "김민수님, 요청하신 보안 감사 자동화 데모 일정을 확인드리겠습니다.",
        "source_refs": [0, 1],
    }


def stub_openai_client(payload: dict | str) -> MagicMock:
    message = MagicMock()
    message.content = (
        json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    )
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


def test_get_client_constructs_openai_client(monkeypatch):
    constructed = {}

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            constructed["api_key"] = api_key

    monkeypatch.setattr("backend.services.sales_contact_brief_service.OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        "backend.services.sales_contact_brief_service.settings.openai_api_key", "test-key"
    )

    client = SalesContactBriefService()._get_client()

    assert isinstance(client, FakeOpenAI)
    assert constructed["api_key"] == "test-key"


def test_parse_created_at_returns_none_for_invalid_timestamp():
    assert _parse_created_at("not-a-timestamp") is None


@pytest.mark.asyncio
async def test_generate_sales_contact_brief_from_minutes(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps(
        make_minutes_payload(), ensure_ascii=False
    )
    svc = SalesContactBriefService()
    client = stub_openai_client(make_ai_payload())
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    result = await svc.generate("min-sales-001", redis)

    assert result.task_id == "min-sales-001"
    assert result.contact.name == "김민수"
    assert result.contact.company == "Acme"
    assert result.deal.stage == "demo_requested"
    assert result.customer_needs == ["보안 감사 자동화", "데모 확인"]
    assert result.next_steps[0].task == "다음 주 화요일 데모 일정 확정"
    assert result.source_refs[0].segment_index == 0
    assert redis.set_calls[0][0] == "sales_contact_brief:min-sales-001"
    assert client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }


@pytest.mark.asyncio
async def test_generate_indexes_sales_contact_brief_for_search(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps(
        make_minutes_payload(), ensure_ascii=False
    )
    svc = SalesContactBriefService()
    client = stub_openai_client(make_ai_payload())
    db_session = FakeDbSession()
    indexed = {}
    monkeypatch.setattr(svc, "_get_client", lambda: client)
    monkeypatch.setattr(
        "backend.services.sales_contact_brief_service.ensure_search_index_table",
        lambda connection: indexed.update({"ensured": connection is not None}),
    )

    def fake_index_search_entry(session, **kwargs):
        indexed.update(kwargs)

    monkeypatch.setattr(
        "backend.services.sales_contact_brief_service.index_search_entry",
        fake_index_search_entry,
    )

    await svc.generate("min-sales-001", redis, db_session=db_session)

    assert indexed["ensured"] is True
    assert indexed["task_id"] == "min-sales-001"
    assert indexed["task_type"] == "sales_contact_brief"
    assert indexed["result_data"]["contact"]["company"] == "Acme"
    assert "보안 감사 자동화" in indexed["result_data"]["customer_needs"]
    assert db_session.committed is True
    assert db_session.rolled_back is False


@pytest.mark.asyncio
async def test_generate_ignores_sales_contact_brief_index_failure(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps(
        make_minutes_payload(), ensure_ascii=False
    )
    svc = SalesContactBriefService()
    client = stub_openai_client(make_ai_payload())
    db_session = FakeDbSession()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    def fail_index(connection):
        raise RuntimeError("fts unavailable")

    monkeypatch.setattr(
        "backend.services.sales_contact_brief_service.ensure_search_index_table",
        fail_index,
    )

    result = await svc.generate("min-sales-001", redis, db_session=db_session)

    assert result.contact.company == "Acme"
    assert db_session.committed is False
    assert db_session.rolled_back is True


@pytest.mark.asyncio
async def test_generate_returns_cached_sales_contact_brief(monkeypatch):
    redis = FakeRedis()
    cached = {
        "task_id": "min-sales-001",
        "contact": {"name": "캐시 고객", "company": "Cached Co"},
        "deal": {"stage": "qualified"},
        "customer_needs": ["캐시 니즈"],
        "pain_points": [],
        "objections": [],
        "next_steps": [{"task": "캐시 후속 조치"}],
        "follow_up_message": "캐시 메시지",
        "source_refs": [],
        "created_at": "2026-06-21T00:00:00+00:00",
    }
    redis.values["sales_contact_brief:min-sales-001"] = json.dumps(cached, ensure_ascii=False)
    svc = SalesContactBriefService()
    client = stub_openai_client(make_ai_payload())
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    result = await svc.generate("min-sales-001", redis)

    assert result.contact.name == "캐시 고객"
    client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_returns_cached_sales_contact_brief():
    redis = FakeRedis()
    cached = {
        "task_id": "min-sales-001",
        "contact": {"name": "캐시 고객", "company": "Cached Co"},
        "deal": {"stage": "qualified"},
        "customer_needs": ["캐시 니즈"],
        "pain_points": [],
        "objections": [],
        "next_steps": [{"task": "캐시 후속 조치"}],
        "follow_up_message": "캐시 메시지",
        "source_refs": [],
        "created_at": "2026-06-21T00:00:00+00:00",
    }
    redis.values["sales_contact_brief:min-sales-001"] = json.dumps(cached, ensure_ascii=False)

    result = await SalesContactBriefService().get("min-sales-001", redis)

    assert result.follow_up_message == "캐시 메시지"


@pytest.mark.asyncio
async def test_get_rejects_missing_cached_sales_contact_brief():
    with pytest.raises(SalesContactBriefSourceNotFoundError):
        await SalesContactBriefService().get("missing", FakeRedis())


@pytest.mark.asyncio
async def test_generate_rejects_missing_minutes():
    with pytest.raises(SalesContactBriefSourceNotFoundError):
        await SalesContactBriefService().generate("missing", FakeRedis())


@pytest.mark.asyncio
async def test_generate_rejects_malformed_ai_response(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps(
        make_minutes_payload(), ensure_ascii=False
    )
    svc = SalesContactBriefService()
    monkeypatch.setattr(svc, "_get_client", lambda: stub_openai_client("{bad json"))

    with pytest.raises(SalesContactBriefValidationError):
        await svc.generate("min-sales-001", redis)


@pytest.mark.asyncio
async def test_generate_rejects_empty_minutes_content():
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps({"segments": [], "raw_text": ""})

    with pytest.raises(SalesContactBriefSourceNotFoundError):
        await SalesContactBriefService().generate("min-sales-001", redis)


@pytest.mark.asyncio
async def test_load_minutes_rejects_invalid_json():
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = "{broken"

    with pytest.raises(SalesContactBriefValidationError):
        await SalesContactBriefService().generate("min-sales-001", redis)


@pytest.mark.asyncio
async def test_load_minutes_rejects_non_object_json():
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = "[1, 2, 3]"

    with pytest.raises(SalesContactBriefValidationError):
        await SalesContactBriefService().generate("min-sales-001", redis)


def test_format_transcript_uses_raw_text_without_segments():
    transcript = SalesContactBriefService()._format_transcript({"raw_text": "고객 원문만 있음"})

    assert transcript == "고객 원문만 있음"


def test_format_transcript_skips_non_dict_segments():
    transcript = SalesContactBriefService()._format_transcript(
        {"segments": ["bad", {"speaker": "고객", "start": 3.0, "text": "견적을 원합니다."}]}
    )

    assert "고객" in transcript
    assert "견적을 원합니다." in transcript


def test_extract_source_refs_handles_non_list_segments():
    assert SalesContactBriefService()._extract_source_refs({"segments": "bad"}) == []


def test_extract_source_refs_skips_non_dict_segments():
    refs = SalesContactBriefService()._extract_source_refs(
        {"segments": ["bad", {"speaker": "고객", "start": 1.0, "end": 2.0, "text": "근거"}]}
    )

    assert len(refs) == 1
    assert refs[0].segment_index == 1


def test_parse_response_rejects_non_object_json():
    with pytest.raises(SalesContactBriefValidationError):
        SalesContactBriefService()._parse_response("[1, 2, 3]")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({**make_ai_payload(), "customer_needs": []}, "customer_needs"),
        ({**make_ai_payload(), "next_steps": []}, "next_steps"),
        ({**make_ai_payload(), "follow_up_message": ""}, "follow_up_message"),
    ],
)
@pytest.mark.asyncio
async def test_generate_rejects_incomplete_ai_payload(monkeypatch, payload, message):
    redis = FakeRedis()
    redis.values["task:min:result:min-sales-001"] = json.dumps(
        make_minutes_payload(), ensure_ascii=False
    )
    svc = SalesContactBriefService()
    monkeypatch.setattr(svc, "_get_client", lambda: stub_openai_client(payload))

    with pytest.raises(SalesContactBriefValidationError) as exc_info:
        await svc.generate("min-sales-001", redis, force_refresh=True)

    assert message in str(exc_info.value)
