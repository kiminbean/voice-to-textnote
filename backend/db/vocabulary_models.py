"""
REQ-VOCAB-001: 커스텀 어휘 ORM 모델

Whisper STT 엔진의 initial_prompt에 주입할 도메인 특화 용어 목록.
사용자가 자주 쓰는 고유명사, 전문 용어, 약어 등을 등록하면
STT 정확도가 향상된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class CustomVocabulary(Base):
    """커스텀 어휘 리스트.

    - name: 어휘 리스트 이름 (예: "의료 용어", "프로젝트명")
    - words: 용어 목록 JSON 배열 (예: ["김인빈", "mlx-whisper", "ROS2"])
    """

    __tablename__ = "custom_vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    words: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

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
            f"<CustomVocabulary(id={self.id}, name={self.name!r}, "
            f"words_count={len(self.words)})>"
        )
