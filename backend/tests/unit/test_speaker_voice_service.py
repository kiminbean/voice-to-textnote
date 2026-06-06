"""
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 서비스 단위 테스트

대상: services/speaker_voice_service.py
  - _running_avg (정적 메서드)
  - _merge_sample
  - analyze_upload (analyze_audio mock)
  - create_or_replace_from_samples
  - get_characteristics
  - to_characteristics_response
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.speaker_models  # noqa: F401
import backend.db.speaker_voice_models  # noqa: F401
from backend.db.auth_models import User
from backend.db.models import Base
from backend.db.speaker_models import SpeakerProfile
from backend.db.speaker_voice_models import SpeakerVoiceProfile
from backend.ml.audio_analysis_engine import AudioAnalysisResult
from backend.schemas.speaker import (
    VoiceCharacteristics,
    VoiceProfileCreateRequest,
    VoiceSampleAnalysis,
)
from backend.services.speaker_voice_service import SpeakerVoiceService

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _make_analysis_result(**overrides) -> AudioAnalysisResult:
    """테스트용 AudioAnalysisResult 기본값 생성."""
    defaults = dict(
        filename="test.wav",
        format="wav",
        duration_seconds=5.0,
        sample_rate=16000,
        channels=1,
        sample_width=2,
        bitrate="256k",
        file_size_bytes=160000,
        max_dbfs=-3.0,
        avg_dbfs=-12.5,
        rms_dbfs=-15.0,
        silence_segments=[],
        silence_ratio=0.1,
        speech_ratio=0.9,
        quality_score=0.85,
        quality_issues=[],
        recommendation=None,
    )
    defaults.update(overrides)
    return AudioAnalysisResult(**defaults)


def _make_sample(**overrides) -> VoiceSampleAnalysis:
    """테스트용 VoiceSampleAnalysis 기본값 생성."""
    defaults = dict(
        duration_seconds=5.0,
        sample_rate=16000,
        avg_dbfs=-12.5,
        rms_dbfs=-15.0,
        speech_ratio=0.9,
        silence_ratio=0.1,
        quality_score=0.85,
        quality_issues=[],
    )
    defaults.update(overrides)
    return VoiceSampleAnalysis(**defaults)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_engine():
    """인메모리 SQLite 엔진 — 관련 테이블 전체 생성."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """테스트용 비동기 DB 세션."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_user(db_session):
    """users 테이블 테스트 레코드."""
    user = User(
        id=uuid.uuid4(),
        email="voice-test@example.com",
        password_hash="$2b$12$fakehash",
        display_name="테스트유저",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_speaker(db_session, seeded_user):
    """speaker_profiles 테이블 테스트 레코드 (task_id=None → 전역)."""
    speaker = SpeakerProfile(
        id=uuid.uuid4(),
        user_id=seeded_user.id,
        speaker_label="SPEAKER_00",
        display_name="김철수",
        role="팀장",
        task_id=None,
    )
    db_session.add(speaker)
    await db_session.commit()
    return speaker


@pytest.fixture
def svc() -> SpeakerVoiceService:
    """테스트 대상 서비스 인스턴스."""
    return SpeakerVoiceService()


# ===========================================================================
# _running_avg
# ===========================================================================


class TestRunningAvg:
    """누적 평균 갱신 로직 (순수 함수, mock 불필요)."""

    def test_first_value_when_current_none(self):
        assert SpeakerVoiceService._running_avg(None, 0, 10.0) == 10.0

    def test_first_value_when_count_zero(self):
        assert SpeakerVoiceService._running_avg(999.0, 0, 42.0) == 42.0

    def test_accumulate_two(self):
        result = SpeakerVoiceService._running_avg(10.0, 2, 20.0)
        assert abs(result - 13.333) < 0.01

    def test_new_value_none_preserves_current(self):
        assert SpeakerVoiceService._running_avg(10.0, 5, None) == 10.0

    def test_negative_values(self):
        result = SpeakerVoiceService._running_avg(-20.0, 1, -30.0)
        assert abs(result - (-25.0)) < 0.001


# ===========================================================================
# _merge_sample
# ===========================================================================


class TestMergeSample:
    """단일 샘플 → 프로파일 누적 반영."""

    def test_first_sample_sets_all(self, svc):
        voice = SpeakerVoiceProfile(
            sample_count=0,
            total_duration_seconds=0.0,
        )
        sample = _make_sample()
        svc._merge_sample(voice, sample)

        assert voice.sample_count == 1
        assert voice.total_duration_seconds == 5.0
        assert voice.avg_energy_dbfs == -12.5
        assert voice.avg_rms_dbfs == -15.0
        assert abs(voice.avg_speech_ratio - 0.9) < 0.001
        assert voice.avg_sample_rate == 16000.0
        assert voice.avg_quality_score == 0.85

    def test_accumulates_count_and_duration(self, svc):
        voice = SpeakerVoiceProfile(
            sample_count=2,
            total_duration_seconds=10.0,
            avg_energy_dbfs=-10.0,
            avg_rms_dbfs=-12.0,
            avg_speech_ratio=0.8,
            avg_sample_rate=16000.0,
            avg_quality_score=0.7,
        )
        svc._merge_sample(voice, _make_sample(duration_seconds=3.0))
        assert voice.sample_count == 3
        assert voice.total_duration_seconds == 13.0

    def test_none_optional_fields_preserve_existing(self, svc):
        voice = SpeakerVoiceProfile(
            sample_count=1,
            total_duration_seconds=5.0,
            avg_energy_dbfs=-10.0,
            avg_rms_dbfs=-12.0,
            avg_speech_ratio=0.8,
            avg_sample_rate=16000.0,
            avg_quality_score=0.7,
        )
        svc._merge_sample(voice, _make_sample(sample_rate=None, quality_score=None))
        assert voice.avg_sample_rate == 16000.0
        assert voice.avg_quality_score == 0.7


# ===========================================================================
# create_or_replace_from_samples
# ===========================================================================


class TestCreateOrReplaceFromSamples:
    """분석 결과로 프로파일 생성/초기화."""

    @pytest.mark.asyncio
    async def test_create_new_profile(self, svc, db_session, seeded_speaker):
        payload = VoiceProfileCreateRequest(
            samples=[_make_sample(), _make_sample(duration_seconds=3.0)],
            overwrite=False,
        )
        voice = await svc.create_or_replace_from_samples(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
            payload=payload,
        )
        assert voice.sample_count == 2
        assert voice.total_duration_seconds == 8.0
        assert voice.speaker_profile_id == seeded_speaker.id

    @pytest.mark.asyncio
    async def test_overwrite_resets_then_applies(self, svc, db_session, seeded_speaker):
        # 첫 번째 프로파일 생성
        await svc.create_or_replace_from_samples(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
            payload=VoiceProfileCreateRequest(
                samples=[_make_sample(duration_seconds=10.0)],
                overwrite=False,
            ),
        )
        # overwrite=True → 초기화 후 새 샘플
        voice = await svc.create_or_replace_from_samples(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
            payload=VoiceProfileCreateRequest(
                samples=[_make_sample(duration_seconds=2.0)],
                overwrite=True,
            ),
        )
        assert voice.sample_count == 1
        assert voice.total_duration_seconds == 2.0

    @pytest.mark.asyncio
    async def test_empty_samples_creates_empty_profile(
        self,
        svc,
        db_session,
        seeded_speaker,
    ):
        voice = await svc.create_or_replace_from_samples(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
            payload=VoiceProfileCreateRequest(samples=[], overwrite=False),
        )
        assert voice.sample_count == 0
        assert voice.total_duration_seconds == 0.0

    @pytest.mark.asyncio
    async def test_wrong_user_raises_404(self, svc, db_session, seeded_speaker):
        with pytest.raises(Exception) as exc_info:
            await svc.create_or_replace_from_samples(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=uuid.uuid4(),
                payload=VoiceProfileCreateRequest(samples=[], overwrite=False),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sample_limit_exceeded_raises_409(
        self,
        svc,
        db_session,
        seeded_speaker,
    ):
        """환경변수로 샘플 한도를 1로 설정 후 2개 샘플 주입 → 409."""
        with patch(
            "backend.services.speaker_voice_service._get_max_samples_per_profile",
            return_value=1,
        ):
            with pytest.raises(Exception) as exc_info:
                await svc.create_or_replace_from_samples(
                    session=db_session,
                    speaker_id=seeded_speaker.id,
                    user_id=seeded_speaker.user_id,
                    payload=VoiceProfileCreateRequest(
                        samples=[_make_sample(), _make_sample()],
                        overwrite=False,
                    ),
                )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_nonexistent_speaker_raises_404(self, svc, db_session, seeded_user):
        with pytest.raises(Exception) as exc_info:
            await svc.create_or_replace_from_samples(
                session=db_session,
                speaker_id=uuid.uuid4(),
                user_id=seeded_user.id,
                payload=VoiceProfileCreateRequest(samples=[], overwrite=False),
            )
        assert exc_info.value.status_code == 404


# ===========================================================================
# get_characteristics
# ===========================================================================


class TestGetCharacteristics:
    """음성 특성 조회."""

    @pytest.mark.asyncio
    async def test_existing_profile(self, svc, db_session, seeded_speaker):
        await svc.create_or_replace_from_samples(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
            payload=VoiceProfileCreateRequest(samples=[_make_sample()], overwrite=False),
        )
        voice = await svc.get_characteristics(
            session=db_session,
            speaker_id=seeded_speaker.id,
            user_id=seeded_speaker.user_id,
        )
        assert voice.sample_count == 1
        assert voice.total_duration_seconds == 5.0

    @pytest.mark.asyncio
    async def test_no_profile_raises_404(self, svc, db_session, seeded_speaker):
        with pytest.raises(Exception) as exc_info:
            await svc.get_characteristics(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=seeded_speaker.user_id,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_user_raises_404(self, svc, db_session, seeded_speaker):
        with pytest.raises(Exception) as exc_info:
            await svc.get_characteristics(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=uuid.uuid4(),
            )
        assert exc_info.value.status_code == 404


# ===========================================================================
# to_characteristics_response
# ===========================================================================


class TestToCharacteristicsResponse:
    """ORM 객체 → Pydantic 응답 스키마 변환."""

    def test_full_conversion(self):
        sid = uuid.uuid4()
        now = datetime.now(UTC)
        voice = SpeakerVoiceProfile(
            id=uuid.uuid4(),
            speaker_profile_id=sid,
            sample_count=3,
            total_duration_seconds=15.0,
            avg_energy_dbfs=-12.0,
            avg_rms_dbfs=-14.0,
            avg_speech_ratio=0.85,
            avg_sample_rate=16000.0,
            avg_quality_score=0.9,
            features={"pitch_mean": 200.0},
        )
        # in-memory 객체에는 default가 자동 적용되지 않으므로 수동 설정
        voice.created_at = now
        voice.updated_at = now

        result = SpeakerVoiceService.to_characteristics_response(voice)

        assert isinstance(result, VoiceCharacteristics)
        assert result.speaker_profile_id == sid
        assert result.sample_count == 3
        assert result.total_duration_seconds == 15.0
        assert result.avg_energy_dbfs == -12.0
        assert result.features == {"pitch_mean": 200.0}

    def test_minimal_profile(self):
        sid = uuid.uuid4()
        now = datetime.now(UTC)
        voice = SpeakerVoiceProfile(
            id=uuid.uuid4(),
            speaker_profile_id=sid,
            sample_count=0,
            total_duration_seconds=0.0,
        )
        voice.created_at = now
        voice.updated_at = now

        result = SpeakerVoiceService.to_characteristics_response(voice)
        assert result.sample_count == 0
        assert result.avg_energy_dbfs is None
        assert result.features is None


# ===========================================================================
# analyze_upload
# ===========================================================================


class TestAnalyzeUpload:
    """오디오 업로드 분석 (analyze_audio mock 필요)."""

    @pytest.mark.asyncio
    async def test_successful_wav_upload(self, svc, db_session, seeded_speaker):
        mock_result = _make_analysis_result()
        upload = MagicMock()
        upload.filename = "voice.wav"
        upload.read = AsyncMock(side_effect=[b"fake-audio-data", b""])

        with patch(
            "backend.ml.audio_analysis_engine.analyze_audio",
            return_value=mock_result,
        ):
            sample, voice = await svc.analyze_upload(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=seeded_speaker.user_id,
                upload=upload,
            )

        assert sample.duration_seconds == 5.0
        assert sample.sample_rate == 16000
        assert voice.sample_count == 1
        assert voice.total_duration_seconds == 5.0
        assert voice.speaker_profile_id == seeded_speaker.id

    @pytest.mark.asyncio
    async def test_bad_extension_raises_400(self, svc, db_session, seeded_speaker):
        upload = MagicMock()
        upload.filename = "document.pdf"
        upload.read = AsyncMock(return_value=b"")

        with pytest.raises(Exception) as exc_info:
            await svc.analyze_upload(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=seeded_speaker.user_id,
                upload=upload,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_file_too_large_raises_413(self, svc, db_session, seeded_speaker):
        upload = MagicMock()
        upload.filename = "huge.wav"
        # max_bytes=1 로 설정 → 청크 1바이트라도 초과
        upload.read = AsyncMock(side_effect=[b"x" * 100, b""])

        with patch(
            "backend.services.speaker_voice_service._get_max_sample_bytes",
            return_value=1,
        ):
            with pytest.raises(Exception) as exc_info:
                await svc.analyze_upload(
                    session=db_session,
                    speaker_id=seeded_speaker.id,
                    user_id=seeded_speaker.user_id,
                    upload=upload,
                )
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_analyze_audio_error_raises_422(
        self,
        svc,
        db_session,
        seeded_speaker,
    ):
        upload = MagicMock()
        upload.filename = "corrupt.wav"
        upload.read = AsyncMock(side_effect=[b"bad-data", b""])

        with patch(
            "backend.ml.audio_analysis_engine.analyze_audio",
            side_effect=ValueError("오디오 디코딩 실패"),
        ):
            with pytest.raises(Exception) as exc_info:
                await svc.analyze_upload(
                    session=db_session,
                    speaker_id=seeded_speaker.id,
                    user_id=seeded_speaker.user_id,
                    upload=upload,
                )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_wrong_user_raises_404(self, svc, db_session, seeded_speaker):
        upload = MagicMock()
        upload.filename = "voice.wav"

        with pytest.raises(Exception) as exc_info:
            await svc.analyze_upload(
                session=db_session,
                speaker_id=seeded_speaker.id,
                user_id=uuid.uuid4(),
                upload=upload,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sample_limit_reached_raises_409(
        self,
        svc,
        db_session,
        seeded_speaker,
    ):
        """이미 샘플 한도 도달 상태에서 업로드 → 409."""
        mock_result = _make_analysis_result()
        upload = MagicMock()
        upload.filename = "voice.wav"
        upload.read = AsyncMock(side_effect=[b"data", b""])

        with (
            patch(
                "backend.services.speaker_voice_service._get_max_samples_per_profile",
                return_value=0,
            ),
            patch(
                "backend.ml.audio_analysis_engine.analyze_audio",
                return_value=mock_result,
            ),
        ):
            with pytest.raises(Exception) as exc_info:
                await svc.analyze_upload(
                    session=db_session,
                    speaker_id=seeded_speaker.id,
                    user_id=seeded_speaker.user_id,
                    upload=upload,
                )
        assert exc_info.value.status_code == 409


class TestEnvVarFallbacks:
    """환경변수 파싱 예외 폴백 테스트"""

    def test_max_sample_bytes_fallback_on_invalid_env(self, monkeypatch):
        """잘못된 SPEAKER_VOICE_MAX_SAMPLE_MB → 기본 25MB"""
        from backend.services.speaker_voice_service import _get_max_sample_bytes

        monkeypatch.setenv("SPEAKER_VOICE_MAX_SAMPLE_MB", "not_a_number")
        assert _get_max_sample_bytes() == 25 * 1024 * 1024

    def test_max_samples_per_profile_fallback_on_invalid_env(self, monkeypatch):
        """잘못된 SPEAKER_VOICE_MAX_SAMPLES_PER_PROFILE → 기본 100"""
        from backend.services.speaker_voice_service import _get_max_samples_per_profile

        monkeypatch.setenv("SPEAKER_VOICE_MAX_SAMPLES_PER_PROFILE", "xyz")
        assert _get_max_samples_per_profile() == 100
