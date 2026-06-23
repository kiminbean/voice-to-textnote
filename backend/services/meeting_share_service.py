"""
SPEC-TEAM-001 REQ-TEAM-005: 회의록 공유 서비스

- share_meeting: 회의록을 팀에 공유
- unshare_meeting: 회의록 팀 공유 해제
- list_team_meetings: 팀에 공유된 회의록 목록 (페이지네이션)
- list_user_meetings: 사용자 소유 회의록 목록 (페이지네이션)
- get_or_create_ownership: 소유권 레코드 조회 또는 생성
- is_meeting_owner: 회의록 소유자 여부 확인
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.auth_models import MeetingOwnership, Team, TeamMember
from backend.db.models import TaskResult
from backend.services.team_service import normalize_sharing_policy


class MeetingShareService:
    """회의록 공유 CRUD 서비스"""

    async def get_or_create_ownership(
        self,
        session: AsyncSession,
        task_id: str,
        user_id: uuid.UUID,
    ) -> MeetingOwnership:
        """
        소유권 레코드를 조회하거나 없으면 생성합니다.

        Args:
            session: DB 세션
            task_id: 작업 ID
            user_id: 소유자 UUID

        Returns:
            MeetingOwnership 인스턴스
        """
        await self._require_task_result(session, task_id)

        result = await session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.owner_id == user_id,
                MeetingOwnership.team_id.is_(None),
            )
        )
        ownership = result.scalar_one_or_none()

        if ownership is None:
            ownership = MeetingOwnership()
            ownership.id = uuid.uuid4()
            ownership.task_id = task_id
            ownership.owner_id = user_id
            ownership.team_id = None
            ownership.shared_at = None
            session.add(ownership)
            await session.commit()

        return ownership

    async def is_meeting_owner(
        self,
        session: AsyncSession,
        task_id: str,
        user_id: uuid.UUID,
    ) -> bool:
        """
        사용자가 해당 회의록의 소유자인지 확인합니다.

        Args:
            session: DB 세션
            task_id: 작업 ID
            user_id: 사용자 UUID

        Returns:
            소유자이면 True
        """
        result = await session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.owner_id == user_id,
                MeetingOwnership.team_id.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None

    async def share_meeting(
        self,
        session: AsyncSession,
        task_id: str,
        owner_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> MeetingOwnership:
        """
        회의록을 팀에 공유합니다.

        이미 같은 팀에 공유된 경우 409 Conflict를 반환합니다.

        Args:
            session: DB 세션
            task_id: 작업 ID
            owner_id: 소유자 UUID
            team_id: 공유할 팀 UUID

        Returns:
            생성된 MeetingOwnership 인스턴스

        Raises:
            HTTPException(404): 회의록이 존재하지 않는 경우
            HTTPException(409): 이미 같은 팀에 공유된 경우
        """
        await self._require_task_result(session, task_id)
        if not await self.is_meeting_owner(session, task_id, owner_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="회의록 소유자만 공유할 수 있습니다",
            )

        # 중복 공유 확인
        existing_result = await session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.team_id == team_id,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 해당 팀에 공유된 회의록입니다",
            )

        # 새 공유 레코드 생성
        ownership = MeetingOwnership()
        ownership.id = uuid.uuid4()
        ownership.task_id = task_id
        ownership.owner_id = owner_id
        ownership.team_id = team_id
        ownership.shared_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(ownership)
        await session.commit()

        return ownership

    async def apply_default_team_sharing_policy(
        self,
        session: AsyncSession,
        task_id: str,
        owner_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Apply team_default sharing policies to a newly created meeting artifact.

        Existing meetings are intentionally unaffected. The owner record is created
        first so private ownership remains explicit even when no team defaults apply.
        """
        owner_created = await self._ensure_owner_record(session, task_id, owner_id)

        teams_result = await session.execute(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == owner_id)
        )
        teams = teams_result.scalars().all()
        default_team_ids = [
            team.id
            for team in teams
            if normalize_sharing_policy(team.sharing_policy)["default_visibility"]
            == "team_default"
        ]
        if not default_team_ids:
            if owner_created:
                await session.commit()
            return []

        applied: list[uuid.UUID] = []
        for team_id in default_team_ids:
            existing_result = await session.execute(
                select(MeetingOwnership).where(
                    MeetingOwnership.task_id == task_id,
                    MeetingOwnership.team_id == team_id,
                )
            )
            if existing_result.scalar_one_or_none() is not None:
                continue

            ownership = MeetingOwnership()
            ownership.id = uuid.uuid4()
            ownership.task_id = task_id
            ownership.owner_id = owner_id
            ownership.team_id = team_id
            ownership.shared_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(ownership)
            applied.append(team_id)

        if owner_created or applied:
            await session.commit()
        return applied

    async def _get_task_result(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> TaskResult | None:
        result = await session.execute(select(TaskResult).where(TaskResult.task_id == task_id))
        return result.scalar_one_or_none()

    async def _require_task_result(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> TaskResult:
        task_result = await self._get_task_result(session, task_id)
        if task_result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="회의록을 찾을 수 없습니다",
            )
        return task_result

    async def _ensure_owner_record(
        self,
        session: AsyncSession,
        task_id: str,
        owner_id: uuid.UUID,
    ) -> bool:
        result = await session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.owner_id == owner_id,
                MeetingOwnership.team_id.is_(None),
            )
        )
        if result.scalar_one_or_none() is not None:
            return False

        ownership = MeetingOwnership()
        ownership.id = uuid.uuid4()
        ownership.task_id = task_id
        ownership.owner_id = owner_id
        ownership.team_id = None
        ownership.shared_at = None
        session.add(ownership)
        return True

    async def unshare_meeting(
        self,
        session: AsyncSession,
        task_id: str,
        team_id: uuid.UUID,
    ) -> bool:
        """
        회의록 팀 공유를 해제합니다.

        Args:
            session: DB 세션
            task_id: 작업 ID
            team_id: 공유 해제할 팀 UUID

        Returns:
            성공 시 True, 레코드 없으면 False
        """
        result = await session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == task_id,
                MeetingOwnership.team_id == team_id,
            )
        )
        ownership = result.scalar_one_or_none()

        if ownership is None:
            return False

        await session.delete(ownership)
        await session.commit()
        return True

    async def list_team_meetings(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        팀에 공유된 회의록 목록을 페이지네이션으로 반환합니다.

        Args:
            session: DB 세션
            team_id: 팀 UUID
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 항목 수

        Returns:
            {items, total, page, page_size} 딕셔너리
        """
        offset = (page - 1) * page_size

        # 전체 개수 조회
        count_stmt = select(func.count(MeetingOwnership.id)).where(
            MeetingOwnership.team_id == team_id
        )
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

        # 페이지네이션 데이터 조회 (task_results JOIN)
        stmt = (
            select(MeetingOwnership, TaskResult)
            .outerjoin(TaskResult, TaskResult.task_id == MeetingOwnership.task_id)
            .where(MeetingOwnership.team_id == team_id)
            .order_by(MeetingOwnership.shared_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        rows = result.all()

        items = [
            {
                "task_id": row[0].task_id,
                "task_type": row[1].task_type if row[1] else None,
                "status": row[1].status if row[1] else None,
                "owner_id": str(row[0].owner_id),
                "team_id": str(row[0].team_id) if row[0].team_id else None,
                "shared_at": row[0].shared_at,
                "created_at": row[0].created_at,
            }
            for row in rows
        ]

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def list_user_meetings(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        사용자 소유 회의록 목록을 페이지네이션으로 반환합니다.

        task_results 테이블에서 소유자 기준 레코드를 조회합니다.

        Args:
            session: DB 세션
            user_id: 사용자 UUID
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지당 항목 수

        Returns:
            {items, total, page, page_size} 딕셔너리
        """
        offset = (page - 1) * page_size

        # 명시적 private 소유권만 "내 회의록"으로 집계한다.
        count_stmt = select(func.count(MeetingOwnership.id)).where(
            MeetingOwnership.owner_id == user_id,
            MeetingOwnership.team_id.is_(None),
        )
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

        stmt = (
            select(MeetingOwnership, TaskResult)
            .outerjoin(TaskResult, TaskResult.task_id == MeetingOwnership.task_id)
            .where(
                MeetingOwnership.owner_id == user_id,
                MeetingOwnership.team_id.is_(None),
            )
            .order_by(MeetingOwnership.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        rows = result.all()

        items = [
            {
                "task_id": row[0].task_id,
                "task_type": row[1].task_type if row[1] else None,
                "status": row[1].status if row[1] else None,
                "owner_id": str(row[0].owner_id),
                "team_id": str(row[0].team_id) if row[0].team_id else None,
                "shared_at": row[0].shared_at,
                "created_at": row[0].created_at,
            }
            for row in rows
        ]

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_team_member_role(
        self,
        session: AsyncSession,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> str | None:
        """
        팀 내 사용자 역할을 반환합니다.

        Args:
            session: DB 세션
            team_id: 팀 UUID
            user_id: 사용자 UUID

        Returns:
            역할 문자열 또는 None (비멤버)
        """
        result = await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member is not None else None
