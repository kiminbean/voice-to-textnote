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

from backend.db.models import TaskResult
from backend.db.speaker_models import SpeakerProfile
from backend.db.speaker_voice_models import SpeakerVoiceProfile
from backend.ml.speaker_embedding_engine import cosine_similarity
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

    @staticmethod
    def _merge_voiceprint_embedding(
        current: list[float] | None,
        current_n: int,
        new_embedding: list[float],
    ) -> list[float]:
        """Running average for fixed-length voiceprint embeddings."""
        if not new_embedding:
            return current or []
        if not current or len(current) != len(new_embedding) or current_n <= 0:
            return [float(value) for value in new_embedding]
        merged = [
            ((float(current[i]) * current_n) + float(new_embedding[i])) / (current_n + 1)
            for i in range(len(new_embedding))
        ]
        norm = sum(value * value for value in merged) ** 0.5
        if norm <= 0:
            return []
        return [round(value / norm, 8) for value in merged]

    async def enroll_voiceprint(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        embedding: list[float],
        source_task_id: str | None = None,
        source_speaker_label: str | None = None,
        embedding_backend: str | None = None,
    ) -> SpeakerVoiceProfile:
        """Attach or update a speaker voiceprint embedding."""
        await self._ensure_speaker_owned(session, speaker_id, user_id)
        voice = await self._load_or_create_voice_profile(session, speaker_id)

        features = dict(voice.features or {})
        voiceprint = dict(features.get("voiceprint") or {})
        count = int(voiceprint.get("sample_count") or 0)
        current_embedding = voiceprint.get("embedding")
        if not isinstance(current_embedding, list):
            current_embedding = None

        merged_embedding = self._merge_voiceprint_embedding(
            current_embedding,
            count,
            embedding,
        )
        voiceprint.update(
            {
                "embedding": merged_embedding,
                "sample_count": count + 1,
                "embedding_backend": embedding_backend or voiceprint.get("embedding_backend"),
                "last_source_task_id": source_task_id,
                "last_source_speaker_label": source_speaker_label,
            }
        )
        features["voiceprint"] = voiceprint
        voice.features = features

        await session.commit()
        await session.refresh(voice)
        return voice

    async def match_voiceprints(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        candidate_embeddings: dict[str, dict],
        *,
        threshold: float,
    ) -> dict[str, dict]:
        """Match diarization speaker embeddings against saved speaker profiles."""
        stmt = (
            select(SpeakerProfile, SpeakerVoiceProfile)
            .join(
                SpeakerVoiceProfile,
                SpeakerVoiceProfile.speaker_profile_id == SpeakerProfile.id,
            )
            .where(SpeakerProfile.user_id == user_id, SpeakerProfile.task_id.is_(None))
        )
        rows = (await session.execute(stmt)).all()

        matches: dict[str, dict] = {}
        for candidate_label, candidate in candidate_embeddings.items():
            candidate_embedding = candidate.get("embedding")
            if not isinstance(candidate_embedding, list):
                continue

            best: tuple[float, SpeakerProfile] | None = None
            for profile, voice in rows:
                voiceprint = (voice.features or {}).get("voiceprint") if voice.features else None
                if not isinstance(voiceprint, dict):
                    continue
                stored_embedding = voiceprint.get("embedding")
                if not isinstance(stored_embedding, list):
                    continue
                score = cosine_similarity(candidate_embedding, stored_embedding)
                if best is None or score > best[0]:
                    best = (score, profile)

            if best is None or best[0] < threshold:
                continue
            score, profile = best
            matches[candidate_label] = {
                "speaker_profile_id": str(profile.id),
                "speaker_label": profile.speaker_label,
                "display_name": profile.display_name,
                "similarity": round(score, 4),
            }
        return matches

    async def enroll_from_task(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        source_task_id: str,
        source_speaker_label: str,
    ) -> SpeakerVoiceProfile | None:
        """Enroll a profile from voiceprints stored on a minutes/diarization result."""
        voiceprint = await self._find_task_voiceprint(
            session,
            source_task_id=source_task_id,
            speaker_label=source_speaker_label,
        )
        if voiceprint is None:
            return None
        embedding = voiceprint.get("embedding")
        if not isinstance(embedding, list):
            return None
        return await self.enroll_voiceprint(
            session=session,
            speaker_id=speaker_id,
            user_id=user_id,
            embedding=[float(value) for value in embedding],
            source_task_id=source_task_id,
            source_speaker_label=source_speaker_label,
            embedding_backend=voiceprint.get("embedding_backend"),
        )

    async def backfill_missing_voiceprints(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> dict[str, object]:
        """Enroll saved global speakers from historical task voiceprints when labels match."""
        profiles = (
            await session.execute(
                select(SpeakerProfile).where(
                    SpeakerProfile.user_id == user_id,
                    SpeakerProfile.task_id.is_(None),
                )
            )
        ).scalars().all()

        scanned = 0
        enrolled = 0
        missing: list[str] = []
        for profile in profiles:
            scanned += 1
            if await self.voiceprint_sample_count(session, profile.id) > 0:
                continue

            voiceprint = await self._find_historical_voiceprint(
                session,
                user_id=user_id,
                speaker_label=profile.speaker_label,
            )
            if voiceprint is None:
                missing.append(profile.speaker_label)
                continue

            embedding = voiceprint.get("embedding")
            if not isinstance(embedding, list):
                missing.append(profile.speaker_label)
                continue

            await self.enroll_voiceprint(
                session=session,
                speaker_id=profile.id,
                user_id=user_id,
                embedding=[float(value) for value in embedding],
                source_task_id=voiceprint.get("source_task_id"),
                source_speaker_label=profile.speaker_label,
                embedding_backend=voiceprint.get("embedding_backend"),
            )
            enrolled += 1

        return {
            "scanned_profiles": scanned,
            "enrolled_profiles": enrolled,
            "skipped_profiles": scanned - enrolled - len(missing),
            "missing_voiceprints": missing,
        }

    async def voiceprint_sample_count(
        self,
        session: AsyncSession,
        speaker_id: uuid.UUID,
    ) -> int:
        voice = (
            await session.execute(
                select(SpeakerVoiceProfile).where(
                    SpeakerVoiceProfile.speaker_profile_id == speaker_id
                )
            )
        ).scalar_one_or_none()
        if voice is None or not isinstance(voice.features, dict):
            return 0
        voiceprint = voice.features.get("voiceprint")
        if not isinstance(voiceprint, dict):
            return 0
        return int(voiceprint.get("sample_count") or 0)

    async def _find_historical_voiceprint(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        speaker_label: str,
    ) -> dict | None:
        rows = (
            await session.execute(
                select(TaskResult)
                .where(TaskResult.status == "completed")
                .order_by(TaskResult.updated_at.desc())
            )
        ).scalars().all()

        for task in rows:
            if not self._task_result_belongs_to_user(task, user_id):
                continue
            if not isinstance(task.result_data, dict):
                continue
            voiceprint = self._voiceprint_from_result(task.result_data, speaker_label)
            if voiceprint is None:
                continue
            voiceprint = dict(voiceprint)
            voiceprint.setdefault("source_task_id", task.task_id)
            return voiceprint
        return None

    @staticmethod
    def _task_result_belongs_to_user(task: TaskResult, user_id: uuid.UUID) -> bool:
        expected = str(user_id)
        for payload in (task.input_metadata, task.result_data):
            if not isinstance(payload, dict):
                continue
            for key in ("user_id", "owner_user_id", "created_by"):
                value = payload.get(key)
                if value is not None and str(value) == expected:
                    return True
        return False

    async def _find_task_voiceprint(
        self,
        session: AsyncSession,
        *,
        source_task_id: str,
        speaker_label: str,
    ) -> dict | None:
        task = (
            await session.execute(select(TaskResult).where(TaskResult.task_id == source_task_id))
        ).scalar_one_or_none()
        if task is None or not isinstance(task.result_data, dict):
            return None

        result_data = task.result_data
        if task.task_type == "minutes":
            direct = self._voiceprint_from_result(result_data, speaker_label)
            if direct is not None:
                return direct
            diarization_task_id = result_data.get("diarization_task_id")
            if diarization_task_id:
                dia_task = (
                    await session.execute(
                        select(TaskResult).where(TaskResult.task_id == str(diarization_task_id))
                    )
                ).scalar_one_or_none()
                if dia_task is not None and isinstance(dia_task.result_data, dict):
                    return self._voiceprint_from_result(dia_task.result_data, speaker_label)
            return None

        return self._voiceprint_from_result(result_data, speaker_label)

    @staticmethod
    def _voiceprint_from_result(result_data: dict, speaker_label: str) -> dict | None:
        voiceprints = result_data.get("voiceprints")
        if isinstance(voiceprints, dict):
            value = voiceprints.get(speaker_label)
            return value if isinstance(value, dict) else None
        if isinstance(voiceprints, list):
            for item in voiceprints:
                if isinstance(item, dict) and item.get("speaker_id") == speaker_label:
                    return item
        return None

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
