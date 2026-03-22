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
            return None

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
