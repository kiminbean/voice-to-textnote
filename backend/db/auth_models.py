"""
SPEC-TEAM-001: 인증 및 팀 관련 ORM 모델

REQ-AUTH-001: User 모델 (회원 가입/인증)
REQ-AUTH-003: RefreshToken 모델 (JWT refresh token rotation)
REQ-TEAM-001: Team 모델
REQ-TEAM-006: TeamMember 모델 (admin/member/viewer 역할)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models import Base, _utcnow


class User(Base):
    """
    SPEC-TEAM-001: 사용자 모델

    이메일/비밀번호 기반 인증 사용자.
    """

    __tablename__ = "users"

    # UUID 기본 키
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 이메일 (유니크 인덱스)
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # bcrypt 해싱된 비밀번호
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # 표시 이름
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 계정 활성화 여부
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # 자동 타임스탬프
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
        return f"<User(id={self.id}, email={self.email!r})>"


class Team(Base):
    """
    SPEC-TEAM-001: 팀 모델

    팀은 여러 User로 구성됩니다.
    생성자는 자동으로 admin 역할로 추가됩니다.
    """

    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 팀 이름
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # 팀 설명 (선택)
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 생성자 ID (users.id 외래 키)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
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
        return f"<Team(id={self.id}, name={self.name!r})>"


class TeamMember(Base):
    """
    SPEC-TEAM-001: 팀 멤버십 모델

    사용자와 팀의 N:M 관계를 나타내며,
    역할(admin/member/viewer)을 포함합니다.
    """

    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 팀 ID (CASCADE 삭제)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 사용자 ID (CASCADE 삭제)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 역할: admin(관리자), member(일반 멤버), viewer(조회 전용)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )

    # 팀 내 user_id 유니크 (중복 멤버 방지)
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role={self.role!r})>"


class RefreshToken(Base):
    """
    SPEC-TEAM-001: JWT Refresh Token 모델

    SHA-256 해시 값으로 저장합니다 (원본 노출 방지).
    로그인/갱신 시 rotation 전략으로 보안을 강화합니다.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # 사용자 ID (CASCADE 삭제)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # SHA-256 해시 (인덱스로 빠른 조회)
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # 만료 시각
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # 폐기 여부 (로그아웃 또는 rotation 시 True)
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, is_revoked={self.is_revoked})>"
