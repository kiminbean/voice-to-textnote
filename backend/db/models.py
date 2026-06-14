"""
DB ORM 모델 - SQLAlchemy 2.0 Mapped 타입 기반

REQ-DB-004: TaskResult 모델
REQ-DB-005: AuditLog 모델
REQ-DB-006: UUID 기본 키, created/updated 타임스탬프
REQ-GUEST-008: TaskResult에 게스트 세션 필드 추가
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """ORM 베이스 클래스"""

    pass


def _utcnow() -> datetime:
    """현재 UTC 시각 반환 (타임존 없는 datetime - SQLite 호환)"""
    return datetime.now(UTC).replace(tzinfo=None)


class ActionItem(Base):
    """
    액션 아이템 관리 모델 (SPEC-ACTION-001).
    """

    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meeting_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:
        return f"<ActionItem(id={self.id}, title={self.title!r}, status={self.status!r})>"


class TaskResult(Base):
    """
    REQ-DB-004: 작업 결과 저장 모델

    Celery 작업 완료 후 결과를 영속화하고,
    Redis 캐시 미스 시 폴백 조회에 사용됩니다.
    """

    __tablename__ = "task_results"

    # REQ-DB-006: UUID 기본 키
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 작업 식별자 (Celery task ID, 유니크 인덱스)
    task_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # 작업 유형 (transcription, diarization, minutes, summary)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # 작업 상태 (pending, processing, completed, failed)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # 입력 메타데이터 (JSON)
    input_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # 결과 데이터 (JSON)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # 오류 메시지 (실패 시)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # REQ-DB-006: 자동 타임스탬프
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

    # 완료 시각 (완료 전 NULL)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # REQ-GUEST-008: 게스트 세션 필드
    # 게스트 요청 여부 (비로그인 임시 사용자)
    is_guest: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    # 게스트 세션 ID (is_guest=True일 때 설정)
    guest_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    def __repr__(self) -> str:
        return f"<TaskResult(id={self.id}, task_id={self.task_id!r}, status={self.status!r})>"


class AuditLog(Base):
    """
    REQ-DB-005: HTTP 감사 로그 모델

    모든 API 요청을 기록합니다.
    """

    __tablename__ = "audit_logs"

    # REQ-DB-006: UUID 기본 키
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 요청 ID (X-Request-ID 헤더)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # HTTP 메서드
    method: Mapped[str] = mapped_column(String(10), nullable=False)

    # 요청 경로
    path: Mapped[str] = mapped_column(String(500), nullable=False)

    # HTTP 상태 코드
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # 클라이언트 IP
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False)

    # 처리 시간 (밀리초)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)

    # 요청 타임스탬프
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, request_id={self.request_id!r}, "
            f"path={self.path!r}, status_code={self.status_code})>"
        )
