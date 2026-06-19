"""
Audio enhancement API contract tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def app_client(fake_redis: FakeRedis):
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    app.dependency_overrides[get_audio_enhancement_service] = lambda: FakeEnhancementService()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


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


def test_get_status_returns_404_for_missing_task(app_client: TestClient) -> None:
    response = app_client.get("/api/v1/enhance/status/missing")

    assert response.status_code == 404


def test_post_rejects_unsupported_extension(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/v1/enhance",
        files={"file": ("sample.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 422
