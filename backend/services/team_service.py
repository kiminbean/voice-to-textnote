"""
SPEC-TEAM-001: 팀 관리 서비스

REQ-TEAM-001: 팀 생성 (creator → admin 역할 자동 부여)
REQ-TEAM-002: 사용자 팀 목록 조회
REQ-TEAM-003: 팀 상세 조회 (멤버 포함)
REQ-TEAM-004: 팀 수정
REQ-TEAM-005: 팀 삭제
REQ-TEAM-006: 팀 내 사용자 역할 조회
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import Team, TeamMember, User


class TeamService:
    """팀 CRUD 서비스"""

    async def create_team(
        self,
        session: AsyncSession,
        name: str,
        description: str | None,
        creator_id: uuid.UUID,
    ) -> Team:
        """
        팀 생성.
        생성자는 자동으로 admin 역할로 팀에 추가됩니다.

        Returns:
            생성된 Team 인스턴스
        """
        # 팀 생성
        team = Team()
        team.id = uuid.uuid4()
        team.name = name
        team.description = description
        team.created_by = creator_id
        session.add(team)

        # 생성자를 admin으로 팀에 추가
        member = TeamMember()
        member.id = uuid.uuid4()
        member.team_id = team.id
        member.user_id = creator_id
        member.role = "admin"
        member.joined_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(member)

        await session.commit()
        return team

    async def list_user_teams(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[dict]:
        """
        사용자가 멤버로 속한 팀 목록 반환 (멤버 수 포함).

        Returns:
            팀 정보 딕셔너리 리스트
        """
        # 팀과 멤버 수를 조인으로 한 번에 조회
        stmt = (
            select(Team, func.count(TeamMember.id).label("member_count"))
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id)
            .group_by(Team.id)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": row[0].id,
                "name": row[0].name,
                "description": row[0].description,
                "created_by": str(row[0].created_by),
                "created_at": row[0].created_at,
                "member_count": row[1],
            }
            for row in rows
        ]

    async def get_team(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
    ) -> Team | None:
        """팀 ID로 단순 조회"""
        result = await session.execute(
            select(Team).where(Team.id == team_id)
        )
        return result.scalar_one_or_none()

    async def get_team_with_members(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
    ) -> dict | None:
        """
        팀 상세 조회 (멤버 목록 포함).

        Returns:
            팀 상세 딕셔너리 또는 None
        """
        # 팀 조회
        team_result = await session.execute(
            select(Team).where(Team.id == team_id)
        )
        team = team_result.scalar_one_or_none()
        if team is None:
            return None  # pragma: no cover

        # 멤버 조회 (User JOIN)
        members_stmt = (
            select(User, TeamMember)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id)
        )
        members_result = await session.execute(members_stmt)
        member_rows = members_result.all()

        members = [
            {
                "user_id": str(row[0].id),
                "email": row[0].email,
                "display_name": row[0].display_name,
                "role": row[1].role,
                "joined_at": row[1].joined_at,
            }
            for row in member_rows
        ]

        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "created_by": str(team.created_by),
            "created_at": team.created_at,
            "member_count": len(members),
            "members": members,
        }

    async def update_team(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Team:
        """
        팀 정보 수정 (부분 업데이트).

        Returns:
            업데이트된 Team 인스턴스
        """
        result = await session.execute(
            select(Team).where(Team.id == team_id)
        )
        team = result.scalar_one_or_none()
        if team is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다")

        if name is not None:
            team.name = name
        if description is not None:
            team.description = description

        await session.commit()
        return team

    async def delete_team(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
    ) -> bool:
        """
        팀 삭제.

        Returns:
            성공 시 True
        """
        result = await session.execute(
            select(Team).where(Team.id == team_id)
        )
        team = result.scalar_one_or_none()
        if team is None:
            return False

        await session.delete(team)
        await session.commit()
        return True

    async def get_user_role(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """
        팀 내 사용자 역할 반환.

        Returns:
            역할 문자열 ('admin', 'member', 'viewer') 또는 None (비멤버)
        """
        result = await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member is not None else None

    # -------------------------------------------------------------------------
    # REQ-TEAM-003: 팀 멤버 관리
    # -------------------------------------------------------------------------

    async def count_admins(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
    ) -> int:
        """
        팀의 admin 멤버 수 반환.

        Returns:
            admin 역할 멤버 수
        """
        result = await session.execute(
            select(func.count(TeamMember.id)).where(
                TeamMember.team_id == team_id,
                TeamMember.role == "admin",
            )
        )
        return result.scalar_one()

    async def add_member(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        email: str,
        role: str,
        invited_by: uuid.UUID,  # noqa: ARG002 - SPEC에서 정의, 향후 audit 로깅용
    ) -> TeamMember:
        """
        이메일로 사용자를 찾아 팀에 추가.

        Args:
            session: DB 세션
            team_id: 대상 팀 ID
            email: 초대할 사용자 이메일
            role: 부여할 역할 (admin/member/viewer)
            invited_by: 초대한 사용자 ID

        Returns:
            생성된 TeamMember 인스턴스

        Raises:
            ValueError: 사용자 미존재(404) 또는 이미 멤버(409)
        """
        # 유효 역할 검증
        if role not in ("admin", "member", "viewer"):
            raise ValueError(f"유효하지 않은 역할입니다: {role}")

        # 이메일로 사용자 조회
        user_result = await session.execute(
            select(User).where(User.email == email)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            raise LookupError(f"이메일 '{email}'에 해당하는 사용자를 찾을 수 없습니다")

        # 이미 멤버인지 확인
        existing_result = await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user.id,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            raise ValueError("이미 팀 멤버입니다")

        # 팀 멤버 추가
        member = TeamMember()
        member.id = uuid.uuid4()
        member.team_id = team_id
        member.user_id = user.id
        member.role = role
        member.joined_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(member)
        await session.commit()
        return member

    async def update_member_role(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        new_role: str,
        requester_id: uuid.UUID,
    ) -> TeamMember:
        """
        팀 멤버의 역할 변경.

        Args:
            session: DB 세션
            team_id: 대상 팀 ID
            user_id: 역할을 변경할 멤버 ID
            new_role: 새 역할 (admin/member/viewer)
            requester_id: 요청자 ID

        Returns:
            업데이트된 TeamMember 인스턴스

        Raises:
            ValueError: 자신의 역할 변경 시도, 마지막 admin 보호, 유효하지 않은 역할
            LookupError: 대상 멤버 미존재
        """
        # 유효 역할 검증
        if new_role not in ("admin", "member", "viewer"):
            raise ValueError(f"유효하지 않은 역할입니다: {new_role}")

        # 자신의 역할 변경 금지
        if requester_id == user_id:
            raise ValueError("자신의 역할은 변경할 수 없습니다")

        # 대상 멤버 조회
        member_result = await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = member_result.scalar_one_or_none()
        if member is None:
            raise LookupError("팀 멤버를 찾을 수 없습니다")

        # admin → 다른 역할로 변경 시 마지막 admin 보호
        if member.role == "admin" and new_role != "admin":
            admin_count = await self.count_admins(session, team_id)
            if admin_count <= 1:
                raise ValueError("마지막 admin의 역할은 변경할 수 없습니다")

        member.role = new_role
        await session.commit()
        return member

    async def remove_member(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        requester_id: uuid.UUID,  # noqa: ARG002 - API 레이어에서 권한 검증, 향후 audit 로깅용
    ) -> bool:
        """
        팀 멤버 제거 (자기 자신 탈퇴 허용).

        Args:
            session: DB 세션
            team_id: 대상 팀 ID
            user_id: 제거할 멤버 ID
            requester_id: 요청자 ID

        Returns:
            성공 시 True

        Raises:
            ValueError: 마지막 admin 제거 시도
            LookupError: 대상 멤버 미존재
        """
        # 대상 멤버 조회
        member_result = await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = member_result.scalar_one_or_none()
        if member is None:
            raise LookupError("팀 멤버를 찾을 수 없습니다")

        # 마지막 admin은 제거 불가
        if member.role == "admin":
            admin_count = await self.count_admins(session, team_id)
            if admin_count <= 1:
                raise ValueError("마지막 admin은 팀에서 나갈 수 없습니다. 다른 admin을 먼저 지정해주세요")

        await session.delete(member)
        await session.commit()
        return True

    async def list_members(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
    ) -> list[dict]:
        """
        팀 멤버 목록 조회 (사용자 정보 포함).

        Returns:
            멤버 정보 딕셔너리 리스트
        """
        stmt = (
            select(User, TeamMember)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "user_id": str(row[0].id),
                "email": row[0].email,
                "display_name": row[0].display_name,
                "role": row[1].role,
                "joined_at": row[1].joined_at,
            }
            for row in rows
        ]
