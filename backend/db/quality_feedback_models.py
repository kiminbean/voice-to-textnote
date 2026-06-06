"""
SPEC-QUALITY-MONITOR-001: 회의록 품질 피드백/이력 ORM 모델

REQ-QM-001: 사용자가 회의록 품질에 대한 피드백을 제출/조회한다.
REQ-QM-002: 품질 점수/등급 시계열을 저장해 추세 분석을 지원한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class QualityFeedback(Base):
    """사용자 피드백 (1~5 별점 + 코멘트 + 카테고리)."""

    __tablename__ = "quality_feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 회의록 task_id (TaskResult.task_id 참조)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 피드백 제출자 (None이면 익명/게스트)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 별점 1~5
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    # 피드백 카테고리 (accuracy, completeness, clarity, structure, other)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")

    # 코멘트 (선택)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (Index("ix_quality_feedbacks_task_created", "task_id", "created_at"),)


class QualityScoreSnapshot(Base):
    """품질 점수 스냅샷 — 추세 분석용 시계열 데이터."""

    __tablename__ = "quality_score_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[str] = mapped_column(String(5), nullable=False)

    # 카테고리별 점수 요약 (각각 0~100)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    structure_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 평가 모드 (lightweight = AI 미사용, full = AI 포함)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="lightweight")

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (Index("ix_quality_snapshots_task_created", "task_id", "created_at"),)
