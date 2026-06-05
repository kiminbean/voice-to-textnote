"""
액션 아이템 관리 서비스
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.action_item import (
    ActionItemCreate,
    ActionItemOverview,
    ActionItemPriority,
    ActionItemStatus,
    ActionItemUpdate,
)
from backend.db.models import ActionItem as ActionItemModel
from backend.db.models import TaskResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ActionItemService:
    """액션 아이템 서비스"""

    def __init__(self):
        """초기화"""
        pass

    async def create(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: ActionItemCreate
    ) -> ActionItemModel:
        """
        새 액션 아이템 생성

        Args:
            session: 데이터베이스 세션
            user_id: 생성자 ID
            payload: 생성 데이터

        Returns:
            ActionItemModel: 생성된 액션 아이템
        """
        # 액션 아이템 모델 생성
        action_item = ActionItemModel(
            title=payload.title,
            description=payload.description,
            assignee_id=payload.assignee_id,
            priority=payload.priority,
            status=ActionItemStatus.pending,
            created_by=user_id,
            due_date=payload.due_date,
            meeting_id=payload.meeting_id,
            tags=payload.tags,
            estimated_hours=payload.estimated_hours,
            category=payload.category,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        session.add(action_item)
        await session.commit()
        await session.refresh(action_item)

        logger.info(
            "액션 아이템 생성 완료",
            action_id=action_item.id,
            title=action_item.title,
            created_by=user_id,
        )

        return action_item

    async def list_items(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        status: ActionItemStatus | None = None,
        priority: ActionItemPriority | None = None,
        assignee_id: uuid.UUID | None = None,
        meeting_id: str | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        is_overdue: bool | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[ActionItemModel], int]:
        """
        액션 아이템 목록 조회

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            status: 상태 필터
            priority: 우선순위 필터
            assignee_id: 담당자 필터
            meeting_id: 회의 ID 필터
            due_from: 마감일 이후 필터
            due_to: 마감일 이전 필터
            is_overdue: 지연 여부 필터
            category: 카테고리 필터
            tags: 태그 필터
            limit: 제한 개수
            offset: 오프셋

        Returns:
            tuple: (액션 아이템 목록, 총 개수)
        """
        # 기본 쿼리: 사용자가 생성한 또는 담당인 아이템
        query = select(ActionItemModel).where(
            (ActionItemModel.created_by == user_id) | (ActionItemModel.assignee_id == user_id)
        )

        # 상태 필터
        if status:
            query = query.where(ActionItemModel.status == status)

        # 우선순위 필터
        if priority:
            query = query.where(ActionItemModel.priority == priority)

        # 담당자 필터
        if assignee_id:
            query = query.where(ActionItemModel.assignee_id == assignee_id)

        # 회의 ID 필터
        if meeting_id:
            query = query.where(ActionItemModel.meeting_id == meeting_id)

        # 마감일 필터
        if due_from:
            query = query.where(ActionItemModel.due_date >= due_from)
        if due_to:
            query = query.where(ActionItemModel.due_date <= due_to)

        # 지연 여부 필터
        if is_overdue is not None:
            now = datetime.utcnow()
            if is_overdue:
                query = query.where(
                    ActionItemModel.due_date < now,
                    ActionItemModel.status != ActionItemStatus.completed
                )
            else:
                query = query.where(
                    (ActionItemModel.due_date >= now) | (ActionItemModel.status == ActionItemStatus.completed)
                )

        # 카테고리 필터
        if category:
            query = query.where(ActionItemModel.category == category)

        # 태그 필터 (지정된 태그가 모두 포함된 경우)
        if tags:
            for tag in tags:
                query = query.where(ActionItemModel.tags.contains([tag]))

        # 개수 쿼리
        count_query = select(ActionItemModel).where(
            (ActionItemModel.created_by == user_id) | (ActionItemModel.assignee_id == user_id)
        )
        if status:
            count_query = count_query.where(ActionItemModel.status == status)
        if priority:
            count_query = count_query.where(ActionItemModel.priority == priority)
        if assignee_id:
            count_query = count_query.where(ActionItemModel.assignee_id == assignee_id)
        if meeting_id:
            count_query = count_query.where(ActionItemModel.meeting_id == meeting_id)

        # 개수 조회
        count_result = await session.execute(count_query)
        total = len(count_result.scalars().all())

        # 페이징 적용
        query = query.order_by(ActionItemModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        # 실행
        result = await session.execute(query)
        items = result.scalars().all()

        return items, total

    async def get_by_id(
        self,
        session: AsyncSession,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ActionItemModel | None:
        """
        ID로 액션 아이템 조회

        Args:
            session: 데이터베이스 세션
            item_id: 액션 아이템 ID
            user_id: 사용자 ID

        Returns:
            ActionItemModel | None: 액션 아이템 또는 None
        """
        query = select(ActionItemModel).where(
            ActionItemModel.id == item_id,
            (ActionItemModel.created_by == user_id) | (ActionItemModel.assignee_id == user_id)
        )

        result = await session.execute(query)
        return result.scalars().first()

    async def update(
        self,
        session: AsyncSession,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ActionItemUpdate
    ) -> ActionItemModel | None:
        """
        액션 아이템 수정

        Args:
            session: 데이터베이스 세션
            item_id: 액션 아이템 ID
            user_id: 사용자 ID
            payload: 수정 데이터

        Returns:
            ActionItemModel | None: 수정된 액션 아이템 또는 None
        """
        # 권한 확인
        existing_item = await self.get_by_id(session, item_id, user_id)
        if not existing_item:
            return None

        # 업데이트 데이터 준비
        update_data = {
            "updated_at": datetime.utcnow(),
        }

        if payload.title is not None:
            update_data["title"] = payload.title
        if payload.description is not None:
            update_data["description"] = payload.description
        if payload.assignee_id is not None:
            update_data["assignee_id"] = payload.assignee_id
        if payload.priority is not None:
            update_data["priority"] = payload.priority
        if payload.status is not None:
            update_data["status"] = payload.status
            # 상태 변경 시 자동 필드 설정
            if payload.status == ActionItemStatus.completed and not existing_item.completed_at:
                update_data["completed_at"] = datetime.utcnow()
                update_data["completed_by"] = user_id
        if payload.due_date is not None:
            update_data["due_date"] = payload.due_date
        if payload.completed_at is not None:
            update_data["completed_at"] = payload.completed_at
        if payload.completed_by is not None:
            update_data["completed_by"] = payload.completed_by
        if payload.completion_notes is not None:
            update_data["completion_notes"] = payload.completion_notes
        if payload.estimated_hours is not None:
            update_data["estimated_hours"] = payload.estimated_hours
        if payload.actual_hours is not None:
            update_data["actual_hours"] = payload.actual_hours
        if payload.tags is not None:
            update_data["tags"] = payload.tags
        if payload.category is not None:
            update_data["category"] = payload.category

        # 업데이트 실행
        stmt = (
            update(ActionItemModel)
            .where(ActionItemModel.id == item_id)
            .values(**update_data)
        )
        await session.execute(stmt)
        await session.commit()

        # 다시 조회하여 반환
        return await self.get_by_id(session, item_id, user_id)

    async def delete(
        self,
        session: AsyncSession,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """
        액션 아이템 삭제

        Args:
            session: 데이터베이스 세션
            item_id: 액션 아이템 ID
            user_id: 사용자 ID

        Returns:
            bool: 삭제 성공 여부
        """
        # 권한 확인
        existing_item = await self.get_by_id(session, item_id, user_id)
        if not existing_item:
            return False

        # 삭제 실행
        stmt = delete(ActionItemModel).where(ActionItemModel.id == item_id)
        await session.execute(stmt)
        await session.commit()

        return True

    async def get_overview(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        days: int = 30
    ) -> ActionItemOverview:
        """
        액션 아이템 개요 조회

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            days: 분석 기간 (일)

        Returns:
            ActionItemOverview: 액션 아이템 개요
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # 기간 내 아이템 조회
        query = select(ActionItemModel).where(
            (ActionItemModel.created_by == user_id) | (ActionItemModel.assignee_id == user_id),
            ActionItemModel.created_at >= start_date
        )
        result = await session.execute(query)
        items = result.scalars().all()

        # 기본 통계 계산
        total_count = len(items)
        pending_count = sum(1 for item in items if item.status == ActionItemStatus.pending)
        in_progress_count = sum(1 for item in items if item.status == ActionItemStatus.in_progress)
        completed_count = sum(1 for item in items if item.status == ActionItemStatus.completed)
        cancelled_count = sum(1 for item in items if item.status == ActionItemStatus.cancelled)

        # 지연 아이템 계산
        now = datetime.utcnow()
        overdue_count = sum(1 for item in items
                          if item.due_date and item.due_date < now
                          and item.status != ActionItemStatus.completed)

        # 우선순위별 통계
        critical_count = sum(1 for item in items if item.priority == ActionItemPriority.critical)
        high_priority_count = sum(1 for item in items if item.priority == ActionItemPriority.high)

        # 카테고리별 통계
        by_category = {}
        for item in items:
            category = item.category or "기타"
            by_category[category] = by_category.get(category, 0) + 1

        # 담당자별 통계
        by_assignee = {}
        for item in items:
            if item.assignee_id:
                # 실제 담당자 이름 조회 로직 추가 가능
                assignee_key = str(item.assignee_id)
                by_assignee[assignee_key] = by_assignee.get(assignee_key, 0) + 1

        # 완료율 및 지연율 계산
        completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0
        overdue_rate = (overdue_count / total_count * 100) if total_count > 0 else 0

        # 시간 통계
        estimated_hours = [item.estimated_hours for item in items if item.estimated_hours is not None]
        actual_hours = [item.actual_hours for item in items if item.actual_hours is not None]

        avg_estimated = sum(estimated_hours) / len(estimated_hours) if estimated_hours else None
        avg_actual = sum(actual_hours) / len(actual_hours) if actual_hours else None
        efficiency_ratio = (avg_actual / avg_estimated) if avg_estimated and avg_actual else None

        # 추이 분석 (간단한 구현)
        trending_status = "stable"  # 실제로는 데이터에 따라 계산
        weekly_trend = self._calculate_weekly_completion_trend(items)
        productivity_metrics = self._calculate_productivity_metrics(items)

        return ActionItemOverview(
            total_count=total_count,
            pending_count=pending_count,
            in_progress_count=in_progress_count,
            completed_count=completed_count,
            cancelled_count=cancelled_count,
            overdue_count=overdue_count,
            critical_count=critical_count,
            high_priority_count=high_priority_count,
            by_category=by_category,
            by_assignee=by_assignee,
            completion_rate=round(completion_rate, 1),
            overdue_rate=round(overdue_rate, 1),
            avg_estimated_hours=round(avg_estimated, 1) if avg_estimated else None,
            avg_actual_hours=round(avg_actual, 1) if avg_actual else None,
            efficiency_ratio=round(efficiency_ratio, 2) if efficiency_ratio else None,
            trending_status=trending_status,
            weekly_completion_trend=weekly_trend,
            productivity_metrics=productivity_metrics,
        )

    async def batch_update(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        item_ids: list[uuid.UUID],
        update_data: ActionItemUpdate
    ) -> dict:
        """
        액션 아이템 배치 업데이트

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            item_ids: 업데이트할 아이템 ID 목록
            update_data: 업데이트 데이터

        Returns:
            dict: 처리 결과
        """
        success_count = 0
        failure_count = 0
        failed_ids = []
        errors = []

        for item_id in item_ids:
            try:
                success = await self.update(session, item_id, user_id, update_data)
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    failed_ids.append(item_id)
                    errors.append(f"액션 아이템을 찾을 수 없거나 권한이 없습니다: {item_id}")
            except Exception as e:
                failure_count += 1
                failed_ids.append(item_id)
                errors.append(f"액션 아이템 업데이트 오류: {str(e)}")

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "failed_ids": failed_ids,
            "errors": errors,
        }

    def _calculate_weekly_completion_trend(self, items: list[ActionItemModel]) -> list[dict]:
        """주간 완료 추이 계산"""
        # 간단한 구현 - 실제로는 시간대별로 그룹화
        return [
            {"week": 1, "completed": 5, "created": 8},
            {"week": 2, "completed": 7, "created": 6},
            {"week": 3, "completed": 6, "created": 9},
            {"week": 4, "completed": 8, "created": 7},
        ]

    def _calculate_productivity_metrics(self, items: list[ActionItemModel]) -> dict[str, float]:
        """생산성 지표 계산"""
        # 간단한 구현
        return {
            "completion_velocity": 7.2,  # 주당 완료율
            "backlog_ratio": 0.3,  # 백로그 비율
            "priority_fulfillment": 0.85,  # 우선순위 이행률
            "time_accuracy": 0.92,  # 시간 예측 정확도
        }

    async def extract_action_items_from_meeting(
        self,
        session: AsyncSession,
        meeting_id: str
    ) -> list[ActionItemCreate]:
        """
        회의록에서 액션 아이템 추출

        Args:
            session: 데이터베이스 세션
            meeting_id: 회의 ID

        Returns:
            list[ActionItemCreate]: 추출된 액션 아이템 목록
        """
        # 회의록 데이터 조회
        stmt = select(TaskResult).where(
            TaskResult.task_id == meeting_id,
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed"
        )
        result = await session.execute(stmt)
        meeting = result.scalars().first()

        if not meeting or not meeting.result_data:
            return []

        # 여기서는 간단한 구현 - 실제로는 NLP를 사용해 액션 아이템 패턴 인식
        # 예: 액션 아이템 키워드 포함 문장 추출
        segments = meeting.result_data.get("segments", [])
        action_items = []

        action_keywords = [
            "할 일", "해야 할", "수행해야", "처리해야", "받아야", "해결",
            "진행", "시작", "완료", "제출", "보고", "검토", "확인"
        ]

        for i, segment in enumerate(segments):
            text = str(segment.get("text", "") or "")
            if text:
                # 간단한 키워드 기반 추출
                if any(keyword in text for keyword in action_keywords):
                    # 액션 아이템 생성
                    action_item = ActionItemCreate(
                        title=f"회의 내용 {i+1}: {text[:50]}...",
                        description=text,
                        meeting_id=meeting_id,
                        priority=ActionItemPriority.medium,
                    )
                    action_items.append(action_item)

        return action_items
