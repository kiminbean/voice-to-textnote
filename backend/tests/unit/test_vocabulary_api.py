"""
REQ-VOCAB-001: 커스텀 어휘 API 및 STT initial_prompt 통합 테스트
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.vocabulary_models  # noqa: F401
from backend.db.models import Base
from backend.db.vocabulary_models import CustomVocabulary

# ---------------------------------------------------------------------------
# 공용 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def _make_app(db_engine) -> FastAPI:
    from backend.app.api.v1.vocabulary import router
    from backend.app.dependencies import get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return app


@pytest.fixture
def client(db_engine):
    app = _make_app(db_engine)
    return TestClient(app)


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def sample_vocab():
    return {
        "name": "의료 용어",
        "words": ["MRI", "CT 스캔", "수술실", "마취과", "응급실"],
    }


# ---------------------------------------------------------------------------
# CRUD 테스트
# ---------------------------------------------------------------------------


class TestVocabularyCreate:
    def test_create_vocabulary(self, client, sample_vocab):
        resp = client.post("/api/v1/vocabulary", json=sample_vocab)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "의료 용어"
        assert len(data["words"]) == 5
        assert "id" in data
        assert "created_at" in data

    def test_create_vocabulary_empty_name_rejected(self, client):
        resp = client.post("/api/v1/vocabulary", json={"name": "", "words": ["test"]})
        assert resp.status_code == 422

    def test_create_vocabulary_empty_words_rejected(self, client):
        resp = client.post("/api/v1/vocabulary", json={"name": "test", "words": []})
        assert resp.status_code == 422


class TestVocabularyList:
    def test_list_vocabularies_empty(self, client):
        resp = client.get("/api/v1/vocabulary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_vocabularies_with_data(self, client, sample_vocab):
        client.post("/api/v1/vocabulary", json=sample_vocab)
        resp = client.get("/api/v1/vocabulary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "의료 용어"


class TestVocabularyGet:
    def test_get_vocabulary_by_id(self, client, sample_vocab):
        create_resp = client.post("/api/v1/vocabulary", json=sample_vocab)
        vocab_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/vocabulary/{vocab_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "의료 용어"

    def test_get_vocabulary_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/vocabulary/{fake_id}")
        assert resp.status_code == 404


class TestVocabularyUpdate:
    def test_update_vocabulary_name(self, client, sample_vocab):
        create_resp = client.post("/api/v1/vocabulary", json=sample_vocab)
        vocab_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/vocabulary/{vocab_id}",
            json={"name": "수정된 용어"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "수정된 용어"

    def test_update_vocabulary_words(self, client, sample_vocab):
        create_resp = client.post("/api/v1/vocabulary", json=sample_vocab)
        vocab_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/vocabulary/{vocab_id}",
            json={"words": ["새단어1", "새단어2"]},
        )
        assert resp.status_code == 200
        assert resp.json()["words"] == ["새단어1", "새단어2"]


class TestVocabularyDelete:
    def test_delete_vocabulary(self, client, sample_vocab):
        create_resp = client.post("/api/v1/vocabulary", json=sample_vocab)
        vocab_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/vocabulary/{vocab_id}")
        assert resp.status_code == 204

        get_resp = client.get(f"/api/v1/vocabulary/{vocab_id}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# initial_prompt 생성 테스트
# ---------------------------------------------------------------------------


class TestVocabularyInitialPrompt:
    @pytest.mark.asyncio
    async def test_get_initial_prompt_joins_words(self, db_session):
        from backend.services.vocabulary_service import VocabularyService

        vocab = CustomVocabulary(name="테스트", words=["ROS2", "MLX", "PyTorch"])
        db_session.add(vocab)
        await db_session.commit()
        await db_session.refresh(vocab)

        service = VocabularyService()
        prompt = await service.get_initial_prompt(db_session, vocab.id)
        assert prompt == "ROS2 MLX PyTorch"

    @pytest.mark.asyncio
    async def test_get_initial_prompt_nonexistent_returns_none(self, db_session):
        from backend.services.vocabulary_service import VocabularyService

        service = VocabularyService()
        prompt = await service.get_initial_prompt(db_session, uuid.uuid4())
        assert prompt is None

    @pytest.mark.asyncio
    async def test_get_initial_prompt_empty_words_returns_none(self, db_session):
        from backend.services.vocabulary_service import VocabularyService

        vocab = CustomVocabulary(name="빈 리스트", words=[])
        db_session.add(vocab)
        await db_session.commit()
        await db_session.refresh(vocab)

        service = VocabularyService()
        prompt = await service.get_initial_prompt(db_session, vocab.id)
        assert prompt is None


# ---------------------------------------------------------------------------
# STT 엔진 initial_prompt 전달 테스트
# ---------------------------------------------------------------------------


class TestSTTInitialPromptPassthrough:
    """mlx_whisper 실제 import 대신 sys.modules mock으로 coverage 간섭 회피"""

    def test_transcribe_passes_initial_prompt_to_mlx(self, monkeypatch):
        import sys
        from unittest.mock import MagicMock

        captured: dict = {}

        def fake_transcribe(path, **kwargs):
            captured.update(kwargs)
            return {"text": "테스트", "segments": [], "language": "ko"}

        fake_mlx = MagicMock()
        fake_mlx.transcribe = fake_transcribe
        monkeypatch.setitem(sys.modules, "mlx_whisper", fake_mlx)

        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        engine._backend = "mlx"
        engine._model_loaded = True
        engine._model_name = "test-model"

        engine.transcribe("/fake/audio.wav", initial_prompt="ROS2 MLX")

        assert captured.get("initial_prompt") == "ROS2 MLX"

    def test_transcribe_omits_initial_prompt_when_none(self, monkeypatch):
        import sys
        from unittest.mock import MagicMock

        captured: dict = {}

        def fake_transcribe(path, **kwargs):
            captured.update(kwargs)
            return {"text": "테스트", "segments": [], "language": "ko"}

        fake_mlx = MagicMock()
        fake_mlx.transcribe = fake_transcribe
        monkeypatch.setitem(sys.modules, "mlx_whisper", fake_mlx)

        from backend.ml.stt_engine import WhisperEngine

        engine = WhisperEngine()
        engine._backend = "mlx"
        engine._model_loaded = True
        engine._model_name = "test-model"

        engine.transcribe("/fake/audio.wav")

        assert "initial_prompt" not in captured
