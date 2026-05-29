"""
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 ORM 모델

REQ-SPEAKER-VOICE-001: 화자 프로필별 음성 특성(음높이, 에너지, 발화 비율 등)을 저장한다.
REQ-SPEAKER-VOICE-002: SpeakerProfile과 1:1 매핑, SpeakerProfile 삭제 시 CASCADE.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class SpeakerVoiceProfile(Base):
    """화자 음성 특성 프로파일.

    오디오 샘플 분석 결과를 집계해 SpeakerProfile에 1:1로 연결한다.

    - sample_count: 누적 분석 샘플 수
    - total_duration_seconds: 누적 분석 음성 길이
    - avg_energy_dbfs / avg_rms_dbfs: 평균 음성 에너지 (낮을수록 조용함)
    - avg_speech_ratio: 0.0 ~ 1.0 (1.0이면 무음이 거의 없음)
    - avg_sample_rate: 분석 샘플 평균 sample rate (Hz)
    - features: 추가 특성 (확장 가능 JSON)
    """

    __tablename__ = "speaker_voice_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # SpeakerProfile과 1:1 매핑 (UNIQUE 제약)
    speaker_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("speaker_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # 누적 통계
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duration_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # 음성 특성 (누적 평균)
    avg_energy_dbfs: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_rms_dbfs: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speech_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_sample_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 확장 특성 (분산, 변동성, 추가 메타데이터)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<SpeakerVoiceProfile(id={self.id}, "
            f"speaker_profile_id={self.speaker_profile_id}, "
            f"samples={self.sample_count})>"
        )
