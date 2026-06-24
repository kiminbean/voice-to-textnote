"""
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 API 테스트

audio_analysis_engine.analyze_audio()는 무거운 의존성(pydub)을 사용하므로
monkeypatch로 stub해 빠른 단위 테스트로 수행한다.
"""

import io
import uuid
from dataclasses import dataclass

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401 - 메타데이터 등록
import backend.db.speaker_models  # noqa: F401
import backend.db.speaker_voice_models  # noqa: F401
from backend.db.auth_models import User
from backend.db.models import Base, TaskResult

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    user_a = User()
    user_a.id = uuid.uuid4()
    user_a.email = "voice-a@example.com"
    user_a.password_hash = "x"
    user_a.display_name = "VoiceA"
    user_a.is_active = True

    user_b = User()
    user_b.id = uuid.uuid4()
    user_b.email = "voice-b@example.com"
    user_b.password_hash = "x"
    user_b.display_name = "VoiceB"
    user_b.is_active = True

    task = TaskResult(
        task_id="dia-voice-001",
        task_type="diarization",
        status="completed",
        result_data={"segments": []},
    )

    async with session_factory() as session:
        session.add_all([user_a, user_b, task])
        await session.commit()

    return {"user_a": user_a, "user_b": user_b, "task_id": task.task_id}


def _make_app(db_engine, acting_user: User) -> FastAPI:
    from backend.app.api.v1.collaboration.speakers import router
    from backend.app.dependencies import get_current_user, get_db_session

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db_session():
        async with session_factory() as session:
            yield session

    async def override_current_user():
        return acting_user

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_current_user] = override_current_user
    return app


@dataclass
class _FakeAnalysis:
    duration_seconds: float = 5.0
    sample_rate: int = 16000
    avg_dbfs: float = -20.0
    rms_dbfs: float = -22.5
    speech_ratio: float = 0.85
    silence_ratio: float = 0.15
    quality_score: float = 0.9
    quality_issues: list | None = None
    # 미사용 필드 - 호환을 위해 추가
    filename: str = "x.wav"
    format: str = "WAV"
    channels: int = 1
    sample_width: int = 2
    bitrate: str | None = None
    file_size_bytes: int = 10000
    max_dbfs: float = -3.0
    silence_segments: list | None = None
    recommendation: str | None = None

    def __post_init__(self):
        if self.quality_issues is None:
            self.quality_issues = []
        if self.silence_segments is None:
            self.silence_segments = []


@pytest.fixture
def stub_analyze_audio(monkeypatch):
    """audio_analysis_engine.analyze_audio() 호출을 가짜 결과로 대체."""

    def _fake(file_path, **_kwargs):
        return _FakeAnalysis()

    monkeypatch.setattr(
        "backend.ml.audio_analysis_engine.analyze_audio",
        _fake,
    )
    return _fake


# ---------------------------------------------------------------------------
# POST /voice-profile (사전 분석 결과 누적)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_voice_profile_with_samples(db_engine, seeded_db):
    """사전 분석된 샘플로 프로파일 초기화."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        resp = client.post(
            f"/api/v1/speakers/{speaker_id}/voice-profile",
            json={
                "samples": [
                    {
                        "duration_seconds": 4.0,
                        "sample_rate": 16000,
                        "avg_dbfs": -18.0,
                        "rms_dbfs": -20.0,
                        "speech_ratio": 0.8,
                        "silence_ratio": 0.2,
                        "quality_score": 0.85,
                    },
                    {
                        "duration_seconds": 6.0,
                        "sample_rate": 16000,
                        "avg_dbfs": -22.0,
                        "rms_dbfs": -24.0,
                        "speech_ratio": 0.9,
                        "silence_ratio": 0.1,
                        "quality_score": 0.95,
                    },
                ]
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["sample_count"] == 2
    assert body["total_duration_seconds"] == pytest.approx(10.0)
    assert body["avg_energy_dbfs"] == pytest.approx(-20.0, abs=0.01)
    assert body["avg_speech_ratio"] == pytest.approx(0.85, abs=0.01)


@pytest.mark.asyncio
async def test_create_speaker_with_enrollment_task_stores_voiceprint(db_engine, seeded_db):
    """화자 생성 시 현재 회의 voiceprint를 전역 프로필에 등록."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            [
                TaskResult(
                    task_id="dia-enroll-001",
                    task_type="diarization",
                    status="completed",
                    input_metadata={"user_id": str(seeded_db["user_a"].id)},
                    result_data={
                        "voiceprints": {
                            "SPEAKER_07": {
                                "embedding": [1.0, 0.0, 0.0],
                                "embedding_backend": "test",
                            }
                        }
                    },
                ),
                TaskResult(
                    task_id="min-enroll-001",
                    task_type="minutes",
                    status="completed",
                    result_data={"diarization_task_id": "dia-enroll-001"},
                ),
            ]
        )
        await session.commit()

    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={
                "speaker_label": "SPEAKER_07",
                "display_name": "영자",
                "enrollment_task_id": "min-enroll-001",
            },
        )
        speaker_id = sp.json()["id"]
        resp = client.get(f"/api/v1/speakers/{speaker_id}/voice-characteristics")

    assert sp.status_code == 201
    assert sp.json()["voiceprint_enrollment_status"] == "enrolled"
    assert sp.json()["voiceprint_sample_count"] == 1
    assert resp.status_code == 200
    voiceprint = resp.json()["features"]["voiceprint"]
    assert voiceprint["embedding"] == [1.0, 0.0, 0.0]
    assert voiceprint["last_source_speaker_label"] == "SPEAKER_07"


@pytest.mark.asyncio
async def test_backfill_speaker_voiceprints_enrolls_existing_profile(db_engine, seeded_db):
    """기존 이름-only 프로필을 과거 voiceprint로 보강."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            TaskResult(
                task_id="dia-backfill-api-001",
                task_type="diarization",
                status="completed",
                input_metadata={"user_id": str(seeded_db["user_a"].id)},
                result_data={
                    "voiceprints": {
                        "SPEAKER_03": {
                            "embedding": [0.0, 1.0, 0.0],
                            "embedding_backend": "test",
                        }
                    }
                },
            )
        )
        await session.commit()

    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_03", "display_name": "철수"},
        )
        speaker_id = sp.json()["id"]
        backfill = client.post("/api/v1/speakers/voiceprints/backfill")
        resp = client.get(f"/api/v1/speakers/{speaker_id}/voice-characteristics")

    assert backfill.status_code == 200
    assert backfill.json()["enrolled_profiles"] == 1
    assert resp.status_code == 200
    assert resp.json()["features"]["voiceprint"]["embedding"] == [0.0, 1.0, 0.0]


@pytest.mark.asyncio
async def test_voice_profile_overwrite_resets_counters(db_engine, seeded_db):
    """overwrite=True 시 누적값이 초기화된다."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_01", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        client.post(
            f"/api/v1/speakers/{speaker_id}/voice-profile",
            json={
                "samples": [{"duration_seconds": 3.0, "sample_rate": 16000, "speech_ratio": 0.5}]
            },
        )
        # overwrite
        resp = client.post(
            f"/api/v1/speakers/{speaker_id}/voice-profile",
            json={
                "overwrite": True,
                "samples": [{"duration_seconds": 7.0, "sample_rate": 16000, "speech_ratio": 0.9}],
            },
        )

    body = resp.json()
    assert body["sample_count"] == 1
    assert body["total_duration_seconds"] == pytest.approx(7.0)
    assert body["avg_speech_ratio"] == pytest.approx(0.9, abs=0.001)


# ---------------------------------------------------------------------------
# GET /voice-characteristics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_voice_characteristics_404_before_creation(db_engine, seeded_db):
    """프로파일 없을 때 404."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        resp = client.get(f"/api/v1/speakers/{speaker_id}/voice-characteristics")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_voice_characteristics_after_creation(db_engine, seeded_db):
    """프로파일 생성 후 정상 조회."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        client.post(
            f"/api/v1/speakers/{speaker_id}/voice-profile",
            json={"samples": [{"duration_seconds": 5.0, "sample_rate": 16000}]},
        )

        resp = client.get(f"/api/v1/speakers/{speaker_id}/voice-characteristics")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_count"] == 1


@pytest.mark.asyncio
async def test_voice_profile_ownership_isolation(db_engine, seeded_db):
    """다른 사용자의 화자 프로파일에 접근 시 404."""
    app_a = _make_app(db_engine, seeded_db["user_a"])
    app_b = _make_app(db_engine, seeded_db["user_b"])

    with TestClient(app_a) as client_a:
        sp = client_a.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "A의 화자"},
        )
        speaker_id = sp.json()["id"]

    with TestClient(app_b) as client_b:
        resp = client_b.post(
            f"/api/v1/speakers/{speaker_id}/voice-profile",
            json={"samples": []},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /analyze-samples (오디오 업로드 분석)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_samples_unsupported_format(db_engine, seeded_db, stub_analyze_audio):
    """지원하지 않는 확장자 → 400."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        resp = client.post(
            f"/api/v1/speakers/{speaker_id}/analyze-samples",
            files={"file": ("bad.exe", io.BytesIO(b"\x00\x01"), "application/octet-stream")},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_analyze_samples_success(db_engine, seeded_db, stub_analyze_audio):
    """오디오 업로드 분석 → 누적 통계 갱신."""
    app = _make_app(db_engine, seeded_db["user_a"])
    with TestClient(app) as client:
        sp = client.post(
            "/api/v1/speakers",
            json={"speaker_label": "SPEAKER_00", "display_name": "테스트"},
        )
        speaker_id = sp.json()["id"]

        resp = client.post(
            f"/api/v1/speakers/{speaker_id}/analyze-samples",
            files={"file": ("sample.wav", io.BytesIO(b"RIFF" + b"\x00" * 100), "audio/wav")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["analyzed"]["sample_rate"] == 16000
    assert body["characteristics"]["sample_count"] == 1
    assert body["characteristics"]["total_duration_seconds"] == pytest.approx(5.0)
