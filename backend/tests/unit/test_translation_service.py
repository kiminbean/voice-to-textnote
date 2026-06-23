from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - register auth metadata
from backend.db.models import Base, TaskResult
from backend.schemas.translation import TranslationSourceType
from backend.services.translation_service import (
    TranslationService,
    TranslationSourceNotFoundError,
    TranslationValidationError,
)


def stub_openai_client(text: str) -> MagicMock:
    message = MagicMock()
    message.content = text
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


class FakeOpenAI:
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def seed_task(session_factory, task_id: str, result_data: dict):
    async with session_factory() as session:
        session.add(
            TaskResult(
                task_id=task_id,
                task_type="minutes",
                status="completed",
                result_data=result_data,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_translate_summary_persists_translation(session_factory, monkeypatch):
    await seed_task(
        session_factory,
        "summary-001",
        {"summary_text": "회의에서 출시 일정과 고객 피드백을 논의했습니다."},
    )
    client = stub_openai_client("The meeting discussed the launch schedule and customer feedback.")
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate(
            "summary-001",
            session,
            target_language="en",
            source_language="ko",
        )

    assert result.task_id == "summary-001"
    assert result.source_type == TranslationSourceType.SUMMARY
    assert result.cached is False
    assert result.translated_text.startswith("The meeting discussed")
    client.chat.completions.create.assert_called_once()

    async with session_factory() as session:
        record = (
            await session.execute(select(TaskResult).where(TaskResult.task_id == "summary-001"))
        ).scalar_one()
        assert record.result_data["translations"]["en"]["target_language"] == "en"
        assert record.result_data["translations"]["summary:en"]["source_type"] == "summary"


@pytest.mark.asyncio
async def test_translate_returns_cached_result_without_openai(session_factory, monkeypatch):
    await seed_task(
        session_factory,
        "minutes-001",
        {
            "segments": [{"speaker": "A", "start": 0.0, "text": "안녕하세요"}],
            "translations": {
                "minutes:en": {
                    "task_id": "minutes-001",
                    "source_type": "minutes",
                    "source_language": "ko",
                    "target_language": "en",
                    "translated_text": "Hello.",
                    "source_excerpt": "[0 | 0.0s | A] 안녕하세요",
                    "cached": False,
                    "created_at": "2026-06-21T00:00:00+00:00",
                }
            },
        },
    )
    client = stub_openai_client("Should not be used")
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate(
            "minutes-001",
            session,
            target_language="EN",
            source_type=TranslationSourceType.MINUTES,
        )

    assert result.cached is True
    assert result.translated_text == "Hello."
    client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_get_cached_auto_translation(session_factory):
    await seed_task(
        session_factory,
        "summary-002",
        {
            "summary_text": "요약",
            "translations": {
                "en": {
                    "task_id": "summary-002",
                    "source_type": "summary",
                    "source_language": None,
                    "target_language": "en",
                    "translated_text": "Summary",
                    "source_excerpt": "요약",
                    "cached": False,
                    "created_at": "2026-06-21T00:00:00+00:00",
                }
            },
        },
    )

    async with session_factory() as session:
        result = await TranslationService().get("summary-002", session, target_language="en")

    assert result.cached is True
    assert result.translated_text == "Summary"


@pytest.mark.asyncio
async def test_translate_minutes_segments_when_summary_absent(session_factory, monkeypatch):
    await seed_task(
        session_factory,
        "minutes-002",
        {
            "segments": [
                {"speaker_name": "진행자", "start": 1.5, "text": "다음 액션 아이템을 확인합니다."},
                {"speaker": "참석자", "text": "금요일까지 초안을 공유하겠습니다."},
            ]
        },
    )
    client = stub_openai_client(
        "[0 | 1.5s | 진행자] Confirm the next action items.\n"
        "[1 | 참석자] I will share the draft by Friday."
    )
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate(
            "minutes-002",
            session,
            target_language="en",
            source_type=TranslationSourceType.MINUTES,
        )

    assert result.source_type == TranslationSourceType.MINUTES
    assert "다음 액션 아이템" in result.source_excerpt


@pytest.mark.asyncio
async def test_translate_forced_summary_source(session_factory, monkeypatch):
    await seed_task(session_factory, "summary-005", {"markdown": "# 회의\n결정 사항"})
    client = stub_openai_client("# Meeting\nDecisions")
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate(
            "summary-005",
            session,
            target_language="en",
            source_type=TranslationSourceType.SUMMARY,
        )

    assert result.source_type == TranslationSourceType.SUMMARY
    assert "# 회의" in result.source_excerpt


@pytest.mark.asyncio
async def test_translate_auto_falls_back_to_minutes_text(session_factory, monkeypatch):
    await seed_task(session_factory, "minutes-003", {"raw_text": "원문 회의록"})
    client = stub_openai_client("Original minutes")
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate("minutes-003", session, target_language="en")

    assert result.source_type == TranslationSourceType.MINUTES
    assert result.source_excerpt == "원문 회의록"


@pytest.mark.asyncio
async def test_translate_minutes_skips_invalid_segment_items(session_factory, monkeypatch):
    await seed_task(
        session_factory,
        "minutes-004",
        {"segments": ["bad", {"text": ""}, {"speaker": "A", "text": "유효한 문장"}]},
    )
    client = stub_openai_client("[2 | A] Valid sentence")
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: client)

    async with session_factory() as session:
        result = await svc.translate(
            "minutes-004",
            session,
            target_language="en",
            source_type=TranslationSourceType.MINUTES,
        )

    assert result.source_excerpt == "[2 | A] 유효한 문장"


@pytest.mark.asyncio
async def test_translate_missing_task_raises_not_found(session_factory):
    async with session_factory() as session:
        with pytest.raises(TranslationSourceNotFoundError):
            await TranslationService().translate("missing", session, target_language="en")


@pytest.mark.asyncio
async def test_get_missing_cached_translation_raises_not_found(session_factory):
    await seed_task(session_factory, "summary-003", {"summary_text": "요약"})

    async with session_factory() as session:
        with pytest.raises(TranslationSourceNotFoundError):
            await TranslationService().get("summary-003", session, target_language="en")


@pytest.mark.asyncio
async def test_translate_empty_source_raises_validation(session_factory):
    await seed_task(session_factory, "empty-001", {"segments": [{"text": "   "}]})

    async with session_factory() as session:
        with pytest.raises(TranslationValidationError):
            await TranslationService().translate(
                "empty-001",
                session,
                target_language="en",
                source_type=TranslationSourceType.MINUTES,
            )


@pytest.mark.asyncio
async def test_translate_empty_summary_source_raises_validation(session_factory):
    await seed_task(session_factory, "summary-006", {"summary_text": "  "})

    async with session_factory() as session:
        with pytest.raises(TranslationValidationError):
            await TranslationService().translate(
                "summary-006",
                session,
                target_language="en",
                source_type=TranslationSourceType.SUMMARY,
            )


@pytest.mark.asyncio
async def test_translate_empty_ai_response_raises_validation(session_factory, monkeypatch):
    await seed_task(session_factory, "summary-004", {"summary_text": "요약"})
    svc = TranslationService()
    monkeypatch.setattr(svc, "_get_client", lambda: stub_openai_client(" "))

    async with session_factory() as session:
        with pytest.raises(TranslationValidationError):
            await svc.translate("summary-004", session, target_language="en")


def test_language_key_normalizes_case_and_space():
    assert TranslationService()._language_key(" EN ") == "en"


def test_get_client_uses_llm_api_key(monkeypatch):
    monkeypatch.setattr("backend.services.translation_service.OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        "backend.services.translation_service.settings",
        SimpleNamespace(
            llm_api_key="zai-test-key",
            llm_base_url="https://api.z.ai/api/coding/paas/v4",
        ),
    )

    client = TranslationService()._get_client()

    assert isinstance(client, FakeOpenAI)
    assert client.api_key == "zai-test-key"
    assert client.base_url == "https://api.z.ai/api/coding/paas/v4"
