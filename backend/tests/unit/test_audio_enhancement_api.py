"""
Audio enhancement API contract tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.audio import enhance
from backend.app.api.v1.audio.enhance import get_audio_enhancement_service, router
from backend.app.dependencies import get_redis_client
from backend.app.error_handlers import register_exception_handlers
from backend.schemas.audio_enhancement import AudioQualityScore, EnhancementResult


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        assert ttl == 86400
        json.loads(value)
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)


class FakeEnhancementService:
    async def enhance_audio(self, file_path, request):
        return EnhancementResult(
            enhanced_task_id="enhanced-task-001",
            original_file_size=file_path.stat().st_size,
            enhanced_file_size=file_path.stat().st_size,
            processing_time_seconds=0.01,
            compression_ratio=1.0,
            quality_scores=AudioQualityScore(
                overall_score=0.8,
                clarity_score=0.7,
                noise_level=0.1,
                volume_level=0.9,
                voice_activity_ratio=0.6,
            ),
            segments=[],
            warnings=[],
            metadata={"enhancement_mode": request.enhancement_mode.value},
        )


class FailingEnhancementService:
    async def enhance_audio(self, _file_path, _request):
        raise RuntimeError("enhancement failed")


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


def _build_client(fake_redis: FakeRedis, service) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    app.dependency_overrides[get_audio_enhancement_service] = lambda: service

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def app_client(fake_redis: FakeRedis):
    with _build_client(fake_redis, FakeEnhancementService()) as client:
        yield client


class EmptyUpload:
    filename = "empty.wav"

    async def read(self, _size: int) -> bytes:
        return b""


class MissingFilenameUpload:
    filename = ""

    async def read(self, _size: int) -> bytes:
        return b"RIFF"


class ChunkedUpload:
    filename = "large.wav"

    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks

    async def read(self, _size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""


def test_enhance_audio_stores_json_status_and_returns_completed_response(
    app_client: TestClient,
    fake_redis: FakeRedis,
) -> None:
    response = app_client.post(
        "/api/v1/enhance",
        files={"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")},
        data={
            "enhancement_mode": "enhanced",
            "noise_reduction_level": "moderate",
            "voice_enhancement": "natural",
            "extract_speech_only": "false",
            "normalize_audio": "true",
            "target_sample_rate": "16000",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["request"]["enhancement_mode"] == "enhanced"
    assert body["result"]["quality_scores"]["overall_score"] == 0.8

    assert len(fake_redis.store) == 1
    stored = json.loads(next(iter(fake_redis.store.values())))
    assert stored["status"] == "completed"
    assert stored["enhancement_request"]["voice_enhancement"] == "natural"
    assert "eval(" not in next(iter(fake_redis.store.values()))


def test_get_audio_enhancement_service_returns_service_instance() -> None:
    assert get_audio_enhancement_service().__class__.__name__ == "AudioEnhancementService"


def test_json_default_stringifies_unknown_values() -> None:
    assert enhance._json_default(object()).startswith("<object object at")


def test_get_status_reads_json_status(app_client: TestClient, fake_redis: FakeRedis) -> None:
    fake_redis.store["task:audio:enhance:task-123"] = json.dumps(
        {
            "task_id": "task-123",
            "status": "processing",
            "progress": 25.0,
            "current_step": "audio_processing",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = app_client.get("/api/v1/enhance/status/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "processing",
        "progress_percent": 25.0,
        "current_step": "audio_processing",
        "estimated_remaining_seconds": None,
        "error_message": None,
    }


def test_get_status_decodes_bytes_status(app_client: TestClient, fake_redis: FakeRedis) -> None:
    fake_redis.store["task:audio:enhance:task-bytes"] = json.dumps(
        {
            "task_id": "task-bytes",
            "status": "processing",
            "progress": 5.0,
            "current_step": "queued",
        }
    ).encode()

    response = app_client.get("/api/v1/enhance/status/task-bytes")

    assert response.status_code == 200
    assert response.json()["current_step"] == "queued"


@pytest.mark.parametrize("raw_status", ["{broken", "[1, 2, 3]"])
def test_get_status_rejects_invalid_status_payloads(
    app_client: TestClient,
    fake_redis: FakeRedis,
    raw_status,
) -> None:
    fake_redis.store["task:audio:enhance:bad"] = raw_status

    response = app_client.get("/api/v1/enhance/status/bad")

    assert response.status_code == 400
    assert "AUDIO_ENHANCE_STATUS_INVALID" in response.text


def test_get_result_rejects_incomplete_task(app_client: TestClient, fake_redis: FakeRedis) -> None:
    fake_redis.store["task:audio:enhance:task-123"] = json.dumps(
        {
            "task_id": "task-123",
            "status": "processing",
            "progress": 25.0,
            "current_step": "audio_processing",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = app_client.get("/api/v1/enhance/results/task-123")

    assert response.status_code == 400
    assert "완료되지 않았습니다" in response.text


def test_get_result_returns_completed_task(app_client: TestClient, fake_redis: FakeRedis) -> None:
    created_at = datetime.now(UTC).isoformat()
    completed_at = datetime.now(UTC).isoformat()
    fake_redis.store["task:audio:enhance:done"] = json.dumps(
        {
            "task_id": "done",
            "status": "completed",
            "enhancement_request": {
                "enhancement_mode": "clean",
                "noise_reduction_level": "light",
                "voice_enhancement": "clear",
                "extract_speech_only": False,
                "target_sample_rate": 16000,
                "normalize_audio": True,
            },
            "result": {
                "enhanced_task_id": "enhanced",
                "original_file_size": 10,
                "enhanced_file_size": 8,
                "processing_time_seconds": 0.1,
                "compression_ratio": 1.25,
                "quality_scores": {
                    "overall_score": 0.9,
                    "clarity_score": 0.8,
                    "noise_level": 0.1,
                    "volume_level": 0.7,
                    "voice_activity_ratio": 0.6,
                },
                "segments": [],
                "warnings": [],
                "metadata": {},
            },
            "created_at": created_at,
            "completed_at": completed_at,
        }
    )

    response = app_client.get("/api/v1/enhance/results/done")

    assert response.status_code == 200
    assert response.json()["result"]["enhanced_task_id"] == "enhanced"


def test_get_status_returns_404_for_missing_task(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/enhance/status/missing")

    assert response.status_code == 404


def test_post_rejects_unsupported_extension(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/enhance",
        files={"file": ("sample.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 422


def test_post_rejects_missing_filename(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/enhance",
        files={"file": ("", b"RIFF", "audio/wav")},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_enhance_audio_rejects_file_object_without_filename(fake_redis: FakeRedis) -> None:
    with pytest.raises(Exception) as exc_info:
        await enhance.enhance_audio(
            file=MissingFilenameUpload(),
            enhancement_mode=enhance.EnhancementMode.ENHANCED,
            noise_reduction_level=enhance.NoiseReductionLevel.MODERATE,
            voice_enhancement=enhance.VoiceEnhancementMode.NATURAL,
            extract_speech_only=False,
            target_sample_rate=16000,
            normalize_audio=True,
            redis_client=fake_redis,
            svc=FakeEnhancementService(),
        )

    assert getattr(exc_info.value, "status_code", None) == 422


def test_post_records_failed_status_when_service_raises(fake_redis: FakeRedis) -> None:
    with _build_client(fake_redis, FailingEnhancementService()) as client:
        response = client.post(
            "/api/v1/enhance",
            files={"file": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")},
        )

    assert response.status_code == 500
    stored = json.loads(next(iter(fake_redis.store.values())))
    assert stored["status"] == "failed"
    assert stored["error_message"] == "enhancement failed"


@pytest.mark.asyncio
async def test_write_upload_rejects_empty_file() -> None:
    with pytest.raises(Exception) as exc_info:
        await enhance._write_upload_to_temp_file(EmptyUpload(), ".wav")

    assert getattr(exc_info.value, "status_code", None) == 422


@pytest.mark.asyncio
async def test_write_upload_rejects_file_over_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(enhance, "MAX_UPLOAD_BYTES", 3)

    with pytest.raises(Exception) as exc_info:
        await enhance._write_upload_to_temp_file(ChunkedUpload([b"12", b"34"]), ".wav")

    assert getattr(exc_info.value, "status_code", None) == 413
