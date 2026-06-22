"""
화자 그룹 관리 모델
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class SpeakerGroup(Base):
    """화자 그룹 테이블"""
    __tablename__ = "speaker_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # HEX color code
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )
    
    # 관계
    members: Mapped[list["SpeakerGroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_speaker_groups_name_user"),
    )


class SpeakerGroupMember(Base):
    """화자 그룹 멤버 테이블"""
    __tablename__ = "speaker_group_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("speaker_groups.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    speaker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("speaker_profiles.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    joined_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    
    # 관계
    group: Mapped["SpeakerGroup"] = relationship(back_populates="members")
    speaker: Mapped["SpeakerProfile"] = relationship(
        back_populates="groups",
        foreign_keys=[speaker_id],
    )
    
    __table_args__ = (
        UniqueConstraint("group_id", "speaker_id", name="uq_speaker_group_members"),
    )