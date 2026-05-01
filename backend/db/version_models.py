"""
회의록 버전 관리 ORM 모델
SPEC-VERSION-001: 회의록 수정 이력 추적
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class MinutesVersion(Base):
    """
    회의록 버전 스냅샷.

    minutes 내용이 수정될 때마다 이전 상태를 저장하여
    변경 이력 조회 및 특정 버전으로 복원을 지원한다.
    version_number는 task_id 기준으로 1부터 단조 증가한다.
    """

    __tablename__ = "minutes_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # 대상 회의록 (task_results.task_id 참조, 삭제 시 연쇄 삭제)
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("task_results.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 버전 번호 (task_id 범위 내에서 1부터 증가)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # 회의록 전체 내용 스냅샷 (JSON)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # 변경 요약 메모 (선택)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 작성자 (users.id 참조, 사용자 삭제 시 NULL 처리)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<MinutesVersion(id={self.id}, task_id={self.task_id!r}, "
            f"version={self.version_number})>"
        )
