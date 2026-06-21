import json
from unittest.mock import MagicMock

import pytest

from backend.schemas.study_pack import StudyPackMode
from backend.services.study_pack_service import (
    StudyPackService,
    StudyPackSourceNotFoundError,
    StudyPackValidationError,
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


def make_minutes_payload() -> dict:
    return {
        "task_id": "min-001",
        "raw_text": "광합성은 빛 에너지를 화학 에너지로 바꾸는 과정입니다.",
        "segments": [
            {
                "speaker_name": "교수",
                "start": 0.0,
                "end": 12.5,
                "text": "광합성은 빛 에너지를 포도당으로 저장하는 과정입니다.",
            },
            {
                "speaker_name": "교수",
                "start": 13.0,
                "end": 24.0,
                "text": "엽록체와 엽록소가 핵심 역할을 합니다.",
            },
        ],
    }


def make_ai_payload() -> dict:
    return {
        "key_concepts": [
            {"term": "광합성", "explanation": "빛 에너지를 화학 에너지로 바꾸는 과정"},
            {"term": "엽록체", "explanation": "식물 세포의 광합성 기관"},
            {"term": "엽록소", "explanation": "빛을 흡수하는 색소"},
        ],
        "flashcards": [
            {"front": "광합성이란?", "back": "빛 에너지를 화학 에너지로 바꾸는 과정"},
            {"front": "엽록체의 역할은?", "back": "광합성이 일어나는 장소"},
            {"front": "엽록소의 역할은?", "back": "빛을 흡수한다"},
        ],
        "quiz_questions": [
            {
                "question": "광합성의 에너지 전환은?",
                "answer": "빛 에너지에서 화학 에너지",
                "difficulty": "easy",
            },
            {
                "question": "엽록체가 중요한 이유는?",
                "answer": "광합성이 일어나는 장소이기 때문",
                "difficulty": "medium",
            },
            {
                "question": "엽록소는 무엇을 흡수하는가?",
                "answer": "빛",
                "difficulty": "easy",
            },
        ],
        "study_notes": "광합성은 엽록체에서 일어나며 엽록소가 빛을 흡수한다.",
    }


def stub_openai_client(payload: dict | str) -> MagicMock:
    message = MagicMock()
    message.content = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else payload
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


@pytest.mark.asyncio
async def test_generate_study_pack_from_minutes(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = json.dumps(make_minutes_payload(), ensure_ascii=False)
    svc = StudyPackService()
    client = stub_openai_client(make_ai_payload())
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    result = await svc.generate("min-001", redis, mode=StudyPackMode.LECTURE)

    assert result.task_id == "min-001"
    assert result.mode == StudyPackMode.LECTURE
    assert len(result.key_concepts) == 3
    assert len(result.flashcards) == 3
    assert len(result.quiz_questions) == 3
    assert result.source_refs[0].segment_index == 0
    assert redis.set_calls[0][0] == "study_pack:min-001"
    assert client.chat.completions.create.call_args.kwargs["response_format"] == {
        "type": "json_object"
    }


@pytest.mark.asyncio
async def test_generate_returns_cached_study_pack(monkeypatch):
    redis = FakeRedis()
    cached = {
        "task_id": "min-001",
        "mode": "general",
        "language": "ko",
        "key_concepts": [{"term": "캐시", "explanation": "저장된 결과"}],
        "flashcards": [{"front": "캐시?", "back": "저장된 결과"}],
        "quiz_questions": [{"question": "캐시?", "answer": "저장된 결과", "difficulty": "easy"}],
        "study_notes": "캐시된 학습팩",
        "source_refs": [],
        "created_at": "2026-06-21T00:00:00+00:00",
    }
    redis.values["study_pack:min-001"] = json.dumps(cached, ensure_ascii=False)
    svc = StudyPackService()
    client = stub_openai_client(make_ai_payload())
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    result = await svc.generate("min-001", redis)

    assert result.study_notes == "캐시된 학습팩"
    client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_returns_cached_study_pack():
    redis = FakeRedis()
    cached = {
        "task_id": "min-001",
        "mode": "general",
        "language": "ko",
        "key_concepts": [{"term": "캐시", "explanation": "저장된 결과"}],
        "flashcards": [{"front": "캐시?", "back": "저장된 결과"}],
        "quiz_questions": [{"question": "캐시?", "answer": "저장된 결과", "difficulty": "easy"}],
        "study_notes": "캐시된 학습팩",
        "source_refs": [],
        "created_at": "2026-06-21T00:00:00+00:00",
    }
    redis.values["study_pack:min-001"] = json.dumps(cached, ensure_ascii=False)
    svc = StudyPackService()

    result = await svc.get("min-001", redis)

    assert result.study_notes == "캐시된 학습팩"


def test_get_client_constructs_openai_client(monkeypatch):
    constructed = {}

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            constructed["api_key"] = api_key

    monkeypatch.setattr("backend.services.study_pack_service.OpenAI", FakeOpenAI)
    monkeypatch.setattr("backend.services.study_pack_service.settings.openai_api_key", "test-key")

    client = StudyPackService()._get_client()

    assert isinstance(client, FakeOpenAI)
    assert constructed["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_generate_rejects_missing_minutes():
    svc = StudyPackService()

    with pytest.raises(StudyPackSourceNotFoundError):
        await svc.generate("missing", FakeRedis())


@pytest.mark.asyncio
async def test_generate_rejects_malformed_ai_response(monkeypatch):
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = json.dumps(make_minutes_payload(), ensure_ascii=False)
    svc = StudyPackService()
    monkeypatch.setattr(svc, "_get_client", lambda: stub_openai_client("{not json"))

    with pytest.raises(StudyPackValidationError):
        await svc.generate("min-001", redis)


@pytest.mark.asyncio
async def test_get_rejects_missing_cached_study_pack():
    svc = StudyPackService()

    with pytest.raises(StudyPackSourceNotFoundError):
        await svc.get("missing", FakeRedis())


@pytest.mark.asyncio
async def test_generate_rejects_empty_minutes_content():
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = json.dumps({"segments": [], "raw_text": ""})
    svc = StudyPackService()

    with pytest.raises(StudyPackSourceNotFoundError):
        await svc.generate("min-001", redis)


@pytest.mark.asyncio
async def test_load_minutes_rejects_invalid_json():
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = "{broken"
    svc = StudyPackService()

    with pytest.raises(StudyPackValidationError):
        await svc.generate("min-001", redis)


@pytest.mark.asyncio
async def test_load_minutes_rejects_non_object_json():
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = "[1, 2, 3]"
    svc = StudyPackService()

    with pytest.raises(StudyPackValidationError):
        await svc.generate("min-001", redis)


def test_format_transcript_uses_raw_text_without_segments():
    svc = StudyPackService()

    transcript = svc._format_transcript({"raw_text": "원문만 있는 회의록"})

    assert transcript == "원문만 있는 회의록"


def test_format_transcript_skips_non_dict_segments():
    svc = StudyPackService()

    transcript = svc._format_transcript(
        {"segments": ["bad", {"speaker": "참석자", "start": 3.0, "text": "핵심 발언"}]}
    )

    assert "참석자" in transcript
    assert "핵심 발언" in transcript


def test_extract_source_refs_handles_non_list_segments():
    svc = StudyPackService()

    assert svc._extract_source_refs({"segments": "bad"}) == []


def test_extract_source_refs_skips_non_dict_segments():
    svc = StudyPackService()

    refs = svc._extract_source_refs(
        {"segments": ["bad", {"speaker": "참석자", "start": 1.0, "end": 2.0, "text": "근거"}]}
    )

    assert len(refs) == 1
    assert refs[0].segment_index == 1


def test_parse_response_rejects_non_object_json():
    svc = StudyPackService()

    with pytest.raises(StudyPackValidationError):
        svc._parse_response("[1, 2, 3]")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "flashcards": [{"front": "Q", "back": "A"}],
                "quiz_questions": [{"question": "Q", "answer": "A"}],
                "study_notes": "노트",
            },
            "key_concepts",
        ),
        (
            {
                "key_concepts": [{"term": "T", "explanation": "E"}],
                "quiz_questions": [{"question": "Q", "answer": "A"}],
                "study_notes": "노트",
            },
            "flashcards",
        ),
        (
            {
                "key_concepts": [{"term": "T", "explanation": "E"}],
                "flashcards": [{"front": "Q", "back": "A"}],
                "study_notes": "노트",
            },
            "quiz_questions",
        ),
        (
            {
                "key_concepts": [{"term": "T", "explanation": "E"}],
                "flashcards": [{"front": "Q", "back": "A"}],
                "quiz_questions": [{"question": "Q", "answer": "A"}],
                "study_notes": "",
            },
            "study_notes",
        ),
    ],
)
@pytest.mark.asyncio
async def test_generate_rejects_incomplete_ai_payload(monkeypatch, payload, message):
    redis = FakeRedis()
    redis.values["task:min:result:min-001"] = json.dumps(make_minutes_payload(), ensure_ascii=False)
    svc = StudyPackService()
    monkeypatch.setattr(svc, "_get_client", lambda: stub_openai_client(payload))

    with pytest.raises(StudyPackValidationError) as exc_info:
        await svc.generate("min-001", redis, force_refresh=True)

    assert message in str(exc_info.value)
