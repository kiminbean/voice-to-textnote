"""
SPEC-TONE-001 tone API 단위 테스트
REQ-TONE-009: SentimentResponse 스키마 변경 금지
REQ-TONE-010: GET /api/v1/tone/{task_id} → ToneResponse, 404 for missing
REQ-TONE-011: tone_model 빈 값 → 503 Service Unavailable
"""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def tone_enabled_settings():
    """tone_model 활성화 — 실제 settings 객체의 속성을 패치"""
    from backend.app.config import settings as real_settings

    original = real_settings.tone_model
    real_settings.tone_model = "egemaps-v2"
    yield real_settings
    real_settings.tone_model = original


def _make_tone_result(task_id: str) -> dict:
    """tone_task가 Redis에 저장하는 완료 결과 구조"""
    return {
        "task_id": task_id,
        "dia_task_id": task_id,
        "status": "completed",
        "segments": [
            {
                "start": 0.0,
                "end": 2.0,
                "speaker": "SPEAKER_00",
                "tone": "calm",
                "confidence": 0.72,
                "prosody_features": {
                    "f0_mean": 180.0,
                    "f0_std": 12.0,
                    "rms_energy": 0.05,
                    "speaking_rate": 50.0,
                },
            },
        ],
        "speakers": [
            {
                "speaker": "SPEAKER_00",
                "dominant_tone": "calm",
                "tone_distribution": {"calm": 1},
                "avg_pitch": 180.0,
                "avg_energy": 0.05,
            },
        ],
        "overall_tone": "calm",
        "generation_time_seconds": 1.23,
        "created_at": "2026-06-14T10:00:00+00:00",
        "completed_at": "2026-06-14T10:00:01+00:00",
    }


def _make_tone_status(task_id: str, status: str = "processing") -> dict:
    return {
        "task_id": task_id,
        "status": status,
        "progress": 0.3,
        "message": "세그먼트별 톤 분석 중...",
        "updated_at": "2026-06-14T10:00:00+00:00",
    }


class MapRedis:
    def __init__(self, values: dict[str, str | None]):
        self.values = values

    async def get(self, key: str):
        return self.values.get(key)


# ---------------------------------------------------------------------------
# 스키마 구조 테스트 (REQ-TONE-009)
# ---------------------------------------------------------------------------


class TestToneSchemaStructure:
    """ToneSegment, SpeakerTone, ToneResponse, ToneStatusResponse 필드 검증"""

    def test_tone_schema_structure(self):
        """ToneSegment/SpeakerTone/ToneResponse/ToneStatusResponse 필수 필드 존재"""
        from backend.schemas.tone import (
            SpeakerTone,
            ToneResponse,
            ToneSegment,
            ToneStatusResponse,
        )

        seg = ToneSegment(
            start=0.0,
            end=2.0,
            speaker="SPEAKER_00",
            tone="calm",
            confidence=0.72,
            prosody_features={"f0_mean": 180.0},
        )
        for field in ("start", "end", "speaker", "tone", "confidence", "prosody_features"):
            assert hasattr(seg, field), f"ToneSegment에 '{field}' 누락"

        sp = SpeakerTone(
            speaker="SPEAKER_00",
            dominant_tone="calm",
            tone_distribution={"calm": 1},
            avg_pitch=180.0,
            avg_energy=0.05,
        )
        for field in ("speaker", "dominant_tone", "tone_distribution", "avg_pitch", "avg_energy"):
            assert hasattr(sp, field), f"SpeakerTone에 '{field}' 누락"

        resp = ToneResponse(
            task_id="test-id",
            status="completed",
            segments=[seg],
            speakers=[sp],
            overall_tone="calm",
        )
        for field in ("task_id", "status", "segments", "speakers", "overall_tone", "error_message"):
            assert hasattr(resp, field), f"ToneResponse에 '{field}' 누락"

        status_resp = ToneStatusResponse(task_id="test-id", status="processing")
        for field in ("task_id", "status", "progress", "message", "error_message"):
            assert hasattr(status_resp, field), f"ToneStatusResponse에 '{field}' 누락"

    def test_sentiment_schema_unchanged(self):
        """SentimentResponse 스키마에 새 required 필드 추가되지 않음 (REQ-TONE-009)"""
        from backend.schemas.sentiment import SentimentResponse

        # 모든 필드가 optional이거나 기본값이 있어야 함 — 새 required 필드 추가 금지
        required_fields = {
            name for name, field in SentimentResponse.model_fields.items() if field.is_required()
        }
        # 기존 required 필드만 존재해야 함 (task_id, status)
        assert required_fields == {"task_id", "status"}, (
            f"SentimentResponse에 새 required 필드 추가됨: {required_fields}"
        )


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트 (REQ-TONE-010, REQ-TONE-011)
# ---------------------------------------------------------------------------


class TestToneApiEndpoints:
    """tone API 라우터 엔드포인트 테스트"""

    def test_get_tone_result_success(self, tone_enabled_settings):
        """GET /api/v1/tone/{task_id} — 결과 존재 시 200 + ToneResponse (REQ-TONE-010)"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        task_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        result_data = _make_tone_result(task_id)
        mock_redis.get = AsyncMock(
            side_effect=lambda key: json.dumps(result_data) if f"result:{task_id}" in key else None
        )

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/tone/{task_id}")
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "completed"
        assert data["overall_tone"] == "calm"
        assert len(data["segments"]) == 1
        assert len(data["speakers"]) == 1

    def test_get_tone_result_not_found(self, tone_enabled_settings):
        """GET /api/v1/tone/{task_id} — 결과 없을 때 404 (REQ-TONE-010)"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        task_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/tone/{task_id}")
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 404

    def test_get_tone_result_503_when_disabled(self):
        """GET /api/v1/tone/{task_id} — tone_model 빈 값 시 503 (REQ-TONE-011, AC-TONE-006)"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        task_id = str(uuid.uuid4())
        mock_redis = AsyncMock()

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            from backend.app.config import settings as real_settings

            original = real_settings.tone_model
            real_settings.tone_model = ""
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/tone/{task_id}")
            real_settings.tone_model = original
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 503
        body = response.json()
        assert "disabled" in body.get("message", "").lower() or "disabled" in str(body).lower()

    def test_get_tone_status(self, tone_enabled_settings):
        """GET /api/v1/tone/{task_id}/status — ToneStatusResponse 반환"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        task_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        status_data = _make_tone_status(task_id, "processing")
        mock_redis.get = AsyncMock(
            side_effect=lambda key: json.dumps(status_data) if f"status:{task_id}" in key else None
        )

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/tone/{task_id}/status")
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "processing"

    def test_get_tone_by_meeting(self, tone_enabled_settings):
        """GET /api/v1/tone/meeting/{meeting_id} — 회의 기반 tone 결과 조회"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        meeting_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        result_data = _make_tone_result(meeting_id)
        mock_redis.get = AsyncMock(
            side_effect=lambda key: (
                json.dumps(result_data) if f"result:{meeting_id}" in key else None
            )
        )

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get(f"/api/v1/tone/meeting/{meeting_id}")
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == meeting_id

    def test_delete_tone_result(self, tone_enabled_settings):
        """DELETE /api/v1/tone/{task_id} — Redis 캐시 삭제"""
        from backend.app.dependencies import get_redis_client
        from backend.app.main import app

        task_id = str(uuid.uuid4())
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        async def override_redis():
            return mock_redis

        app.dependency_overrides[get_redis_client] = override_redis
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.delete(f"/api/v1/tone/{task_id}")
        finally:
            app.dependency_overrides.pop(get_redis_client, None)

        assert response.status_code in (200, 204)
        mock_redis.delete.assert_called_once()


class TestToneMeetingLookupBranches:
    @pytest.mark.asyncio
    async def test_meeting_lookup_uses_direct_tone_result_when_minutes_missing(
        self, tone_enabled_settings, monkeypatch
    ):
        from backend.app.api.v1.analytics import tone

        monkeypatch.setattr(tone, "_lookup_minutes_result_from_db", AsyncMock(return_value=None))
        redis = MapRedis(
            {
                "task:min:result:meeting-1": None,
                "task:tone:result:meeting-1": json.dumps(_make_tone_result("meeting-1")),
            }
        )

        response = await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert response.task_id == "meeting-1"
        assert response.status == "completed"

    @pytest.mark.asyncio
    async def test_meeting_lookup_raises_when_minutes_and_direct_result_missing(
        self, tone_enabled_settings, monkeypatch
    ):
        from backend.app.api.v1.analytics import tone

        monkeypatch.setattr(tone, "_lookup_minutes_result_from_db", AsyncMock(return_value=None))
        redis = MapRedis(
            {
                "task:min:result:meeting-1": None,
                "task:tone:result:meeting-1": None,
            }
        )

        with pytest.raises(Exception) as exc_info:
            await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert getattr(exc_info.value, "status_code", None) == 404

    @pytest.mark.asyncio
    async def test_meeting_lookup_rejects_minutes_without_diarization_id(
        self, tone_enabled_settings
    ):
        from backend.app.api.v1.analytics import tone

        redis = MapRedis({"task:min:result:meeting-1": json.dumps({"task_id": "meeting-1"})})

        with pytest.raises(Exception) as exc_info:
            await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert getattr(exc_info.value, "status_code", None) == 404

    @pytest.mark.asyncio
    async def test_meeting_lookup_returns_processing_status_when_tone_result_missing(
        self, tone_enabled_settings
    ):
        from backend.app.api.v1.analytics import tone

        redis = MapRedis(
            {
                "task:min:result:meeting-1": json.dumps({"diarization_task_id": "dia-1"}),
                "task:tone:result:dia-1": None,
                "task:tone:status:dia-1": json.dumps({"status": "processing"}),
            }
        )

        response = await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert response.task_id == "dia-1"
        assert response.status == "processing"

    @pytest.mark.asyncio
    async def test_meeting_lookup_raises_when_tone_result_and_status_missing(
        self, tone_enabled_settings
    ):
        from backend.app.api.v1.analytics import tone

        redis = MapRedis(
            {
                "task:min:result:meeting-1": json.dumps({"diarization_task_id": "dia-1"}),
                "task:tone:result:dia-1": None,
                "task:tone:status:dia-1": None,
            }
        )

        with pytest.raises(Exception) as exc_info:
            await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert getattr(exc_info.value, "status_code", None) == 404

    @pytest.mark.asyncio
    async def test_meeting_lookup_returns_tone_result_by_diarization_id(
        self, tone_enabled_settings
    ):
        from backend.app.api.v1.analytics import tone

        redis = MapRedis(
            {
                "task:min:result:meeting-1": json.dumps({"diarization_task_id": "dia-1"}),
                "task:tone:result:dia-1": json.dumps(_make_tone_result("dia-1")),
            }
        )

        response = await tone.get_tone_by_meeting("meeting-1", redis_client=redis)

        assert response.task_id == "dia-1"
        assert response.overall_tone == "calm"

    @pytest.mark.asyncio
    async def test_get_tone_status_raises_when_status_missing(self, tone_enabled_settings):
        from backend.app.api.v1.analytics import tone

        with pytest.raises(Exception) as exc_info:
            await tone.get_tone_status("missing", redis_client=MapRedis({}))

        assert getattr(exc_info.value, "status_code", None) == 404

    @pytest.mark.asyncio
    async def test_get_tone_result_returns_processing_status_when_result_missing(
        self, tone_enabled_settings
    ):
        from backend.app.api.v1.analytics import tone

        response = await tone.get_tone_result(
            "tone-1",
            redis_client=MapRedis(
                {
                    "task:tone:result:tone-1": None,
                    "task:tone:status:tone-1": json.dumps({"status": "processing"}),
                }
            ),
        )

        assert response.task_id == "tone-1"
        assert response.status == "processing"


class TestToneMinutesDbFallback:
    @pytest.mark.asyncio
    async def test_lookup_minutes_result_from_db_returns_record_data(self, monkeypatch):
        from backend.app.api.v1.analytics import tone
        from backend.db import sync_engine

        class Session:
            def scalars(self, _stmt):
                return SimpleNamespace(first=lambda: SimpleNamespace(result_data={"dia": "dia-1"}))

        class Context:
            def __enter__(self):
                return Session()

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(sync_engine, "get_sync_session", lambda: Context())

        result = await tone._lookup_minutes_result_from_db("meeting-1", MapRedis({}))

        assert json.loads(result) == {"dia": "dia-1"}

    @pytest.mark.asyncio
    async def test_lookup_minutes_result_from_db_returns_none_without_record(self, monkeypatch):
        from backend.app.api.v1.analytics import tone
        from backend.db import sync_engine

        class Session:
            def scalars(self, _stmt):
                return SimpleNamespace(first=lambda: None)

        class Context:
            def __enter__(self):
                return Session()

            def __exit__(self, *_args):
                return False

        monkeypatch.setattr(sync_engine, "get_sync_session", lambda: Context())

        result = await tone._lookup_minutes_result_from_db("meeting-1", MapRedis({}))

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_minutes_result_from_db_returns_none_on_exception(self, monkeypatch):
        from backend.app.api.v1.analytics import tone
        from backend.db import sync_engine

        def fail_session():
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(sync_engine, "get_sync_session", fail_session)

        result = await tone._lookup_minutes_result_from_db("meeting-1", MapRedis({}))

        assert result is None
