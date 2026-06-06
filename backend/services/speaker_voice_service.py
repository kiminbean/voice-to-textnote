"""
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 서비스

기존 audio_analysis_engine.analyze_audio()를 재활용해 오디오 샘플 특성을 추출하고,
SpeakerVoiceProfile 테이블에 누적 통계를 갱신한다.

환경변수:
- SPEAKER_VOICE_MAX_SAMPLE_MB: 단일 샘플 최대 크기 (기본 25MB)
- SPEAKER_VOICE_MAX_SAMPLES_PER_PROFILE: 누적 가능한 샘플 수 한도 (기본 100)
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.speaker_models import SpeakerProfile
from backend.db.speaker_voice_models import SpeakerVoiceProfile
from backend.schemas.speaker import (
    VoiceCharacteristics,
    VoiceProfileCreateRequest,
    VoiceSampleAnalysis,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _get_max_sample_bytes() -> int:
    """환경변수로 단일 샘플 최대 크기 결정 (MB → bytes)."""
    raw = os.getenv("SPEAKER_VOICE_MAX_SAMPLE_MB", "25")
    try:
        return max(1, int(raw)) * 1024 * 1024
    except (TypeError, ValueError):
        return 25 * 1024 * 1024


def _get_max_samples_per_profile() -> int:
    """환경변수로 누적 샘플 수 한도 결정."""
    raw = os.getenv("SPEAKER_VOICE_MAX_SAMPLES_PER_PROFILE", "100")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 100


# 분석 가능한 오디오 확장자
_ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".opus",
    ".wma",
    ".aac",
    ".webm",
}


class SpeakerVoiceService:
    """화자 음성 프로파일 분석/저장 서비스."""

    async def _ensure_speaker_owned(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeakerProfile:
        """소유권 검증 후 SpeakerProfile 반환."""
        stmt = select(SpeakerProfile).where(SpeakerProfile.id == speaker_id)
        result = await session.execute(stmt)
        speaker = result.scalar_one_or_none()
        if speaker is None or speaker.user_id != user_id:
            raise HTTPException(status_code=404, detail="화자 프로필을 찾을 수 없습니다")
        return speaker

    async def _load_or_create_voice_profile(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
    ) -> SpeakerVoiceProfile:
        """음성 프로파일이 없으면 새로 생성, 있으면 반환."""
        stmt = select(SpeakerVoiceProfile).where(
            SpeakerVoiceProfile.speaker_profile_id == speaker_id
        )
        result = await session.execute(stmt)
        voice = result.scalar_one_or_none()
        if voice is None:
            voice = SpeakerVoiceProfile()
            voice.id = uuid.uuid4()
            voice.speaker_profile_id = speaker_id
            voice.sample_count = 0
            voice.total_duration_seconds = 0.0
            session.add(voice)
        return voice

    @staticmethod
    def _running_avg(
        current: float | None,
        current_n: int,
        new_value: float | None,
    ) -> float | None:
        """누적 평균 갱신. new_value가 None이면 current 유지."""
        if new_value is None:
            return current
        if current is None or current_n <= 0:
            return float(new_value)
        return ((current * current_n) + float(new_value)) / (current_n + 1)

    def _merge_sample(
        self,
        voice: SpeakerVoiceProfile,
        sample: VoiceSampleAnalysis,
    ) -> None:
        """단일 샘플을 음성 프로파일 누적 통계에 반영."""
        n = voice.sample_count
        voice.avg_energy_dbfs = self._running_avg(voice.avg_energy_dbfs, n, sample.avg_dbfs)
        voice.avg_rms_dbfs = self._running_avg(voice.avg_rms_dbfs, n, sample.rms_dbfs)
        voice.avg_speech_ratio = self._running_avg(voice.avg_speech_ratio, n, sample.speech_ratio)
        voice.avg_sample_rate = self._running_avg(
            voice.avg_sample_rate, n, float(sample.sample_rate) if sample.sample_rate else None
        )
        voice.avg_quality_score = self._running_avg(
            voice.avg_quality_score, n, sample.quality_score
        )
        voice.sample_count = n + 1
        voice.total_duration_seconds = (voice.total_duration_seconds or 0.0) + (
            sample.duration_seconds or 0.0
        )

    async def analyze_upload(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        upload: UploadFile,
    ) -> tuple[VoiceSampleAnalysis, SpeakerVoiceProfile]:
        """오디오 업로드 분석 후 프로파일 갱신.

        Returns:
            (분석된 단일 샘플 결과, 갱신된 프로파일)
        """
        # 지연 import: 헤비 의존성(audio engine)을 테스트 환경에서 stub 가능하게
        from backend.ml.audio_analysis_engine import analyze_audio

        await self._ensure_speaker_owned(session, speaker_id, user_id)

        filename = upload.filename or "upload"
        ext = os.path.splitext(filename)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"지원하지 않는 파일 포맷: {ext}. 지원 포맷: "
                    f"{', '.join(sorted(_ALLOWED_EXTENSIONS))}"
                ),
            )

        max_bytes = _get_max_sample_bytes()

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp_path = tmp.name
                read_total = 0
                while chunk := await upload.read(1024 * 1024):
                    read_total += len(chunk)
                    if read_total > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                f"파일 크기 초과: {read_total} bytes "
                                f"(최대 {max_bytes // (1024 * 1024)}MB)"
                            ),
                        )
                    tmp.write(chunk)

            try:
                raw = analyze_audio(file_path=tmp_path)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e

            sample = VoiceSampleAnalysis(
                duration_seconds=raw.duration_seconds,
                sample_rate=raw.sample_rate,
                avg_dbfs=raw.avg_dbfs,
                rms_dbfs=raw.rms_dbfs,
                speech_ratio=raw.speech_ratio,
                silence_ratio=raw.silence_ratio,
                quality_score=raw.quality_score,
                quality_issues=list(raw.quality_issues or []),
            )
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        voice = await self._load_or_create_voice_profile(session, speaker_id)

        if voice.sample_count >= _get_max_samples_per_profile():
            raise HTTPException(
                status_code=409,
                detail=(
                    "누적 가능한 샘플 수 한도를 초과했습니다. "
                    "기존 프로파일을 재설정한 후 다시 시도하세요."
                ),
            )

        self._merge_sample(voice, sample)

        await session.commit()
        await session.refresh(voice)
        return sample, voice

    async def create_or_replace_from_samples(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: VoiceProfileCreateRequest,
    ) -> SpeakerVoiceProfile:
        """이미 분석된 샘플 결과로 프로파일을 초기화하거나 누적한다."""
        await self._ensure_speaker_owned(session, speaker_id, user_id)
        voice = await self._load_or_create_voice_profile(session, speaker_id)

        if payload.overwrite:
            voice.sample_count = 0
            voice.total_duration_seconds = 0.0
            voice.avg_energy_dbfs = None
            voice.avg_rms_dbfs = None
            voice.avg_speech_ratio = None
            voice.avg_sample_rate = None
            voice.avg_quality_score = None
            voice.features = None

        max_samples = _get_max_samples_per_profile()
        for sample in payload.samples:
            if voice.sample_count >= max_samples:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "누적 가능한 샘플 수 한도를 초과했습니다. "
                        "overwrite=True 또는 기존 프로파일 삭제 후 재시도하세요."
                    ),
                )
            self._merge_sample(voice, sample)

        await session.commit()
        await session.refresh(voice)
        return voice

    async def get_characteristics(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SpeakerVoiceProfile:
        """음성 특성 조회. 프로파일 미생성 시 404."""
        await self._ensure_speaker_owned(session, speaker_id, user_id)

        stmt = select(SpeakerVoiceProfile).where(
            SpeakerVoiceProfile.speaker_profile_id == speaker_id
        )
        result = await session.execute(stmt)
        voice = result.scalar_one_or_none()
        if voice is None:
            raise HTTPException(status_code=404, detail="음성 프로파일이 존재하지 않습니다")
        return voice

    @staticmethod
    def to_characteristics_response(
        voice: SpeakerVoiceProfile,
    ) -> VoiceCharacteristics:
        """ORM → 응답 스키마 변환."""
        return VoiceCharacteristics.model_validate(voice)
