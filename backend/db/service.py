"""
결과 영속성 서비스 - ResultService

REQ-DB-009: Celery 작업 완료 후 결과 DB 저장
REQ-DB-010: Redis 캐시 미스 시 DB 폴백 조회
REQ-DB-011: save_result(), get_result(), list_results() 메서드
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TaskResult


class ResultService:
    """
    작업 결과 CRUD 서비스

    비동기 SQLAlchemy 세션을 주입받아 DB 작업을 수행합니다.
    의존성 주입 패턴으로 테스트 가능성을 보장합니다.
    """

    async def save_result(
        self,
        session: AsyncSession,
        task_id: str,
        task_type: str,
        status: str,
        result_data: dict[str, Any] | None = None,
        input_metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> TaskResult:
        """
        작업 결과를 DB에 저장 (upsert)

        동일한 task_id가 이미 존재하면 업데이트합니다.

        Args:
            session: 비동기 DB 세션
            task_id: Celery 작업 ID
            task_type: 작업 유형 (transcription, diarization, ...)
            status: 작업 상태 (pending, processing, completed, failed)
            result_data: 결과 데이터 (JSON)
            input_metadata: 입력 메타데이터 (JSON)
            error_message: 오류 메시지 (실패 시)

        Returns:
            저장된 TaskResult 인스턴스
        """
        # 기존 레코드 조회 (upsert 지원)
        stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            # 신규 삽입
            record = TaskResult(
                task_id=task_id,
                task_type=task_type,
                status=status,
                result_data=result_data,
                input_metadata=input_metadata,
                error_message=error_message,
            )
            session.add(record)
        else:
            # 기존 레코드 업데이트
            record.task_type = task_type
            record.status = status
            record.result_data = result_data
            record.input_metadata = input_metadata
            record.error_message = error_message

            # 완료 상태이면 completed_at 설정
            if status == "completed" and record.completed_at is None:
                record.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.commit()
        await session.refresh(record)
        return record

    async def get_result(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> TaskResult | None:
        """
        task_id로 결과 조회 (REQ-DB-010: Redis 캐시 미스 폴백)

        Args:
            session: 비동기 DB 세션
            task_id: 조회할 작업 ID

        Returns:
            TaskResult 인스턴스 또는 None (없으면)
        """
        stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_results(
        self,
        session: AsyncSession,
        task_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskResult]:
        """
        결과 목록 조회 (페이징 지원)

        Args:
            session: 비동기 DB 세션
            task_type: 작업 유형 필터 (None이면 전체)
            status: 작업 상태 필터 (None이면 전체)
            limit: 최대 조회 개수 (기본 50)
            offset: 건너뛸 개수 (기본 0)

        Returns:
            TaskResult 목록
        """
        stmt = select(TaskResult).order_by(TaskResult.created_at.desc())

        if task_type is not None:
            stmt = stmt.where(TaskResult.task_type == task_type)

        if status is not None:
            stmt = stmt.where(TaskResult.status == status)

        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_results(
        self,
        session: AsyncSession,
        task_type: str | None = None,
        status: str | None = None,
    ) -> int:
        """
        SPEC-HISTORY-001: 조건에 맞는 레코드 총 수 조회

        페이지네이션의 total 값 계산에 사용됩니다.

        Args:
            session: 비동기 DB 세션
            task_type: 작업 유형 필터 (None이면 전체)
            status: 작업 상태 필터 (None이면 전체)

        Returns:
            조건에 맞는 레코드 수
        """
        stmt = select(func.count(TaskResult.id))

        if task_type is not None:
            stmt = stmt.where(TaskResult.task_type == task_type)

        if status is not None:
            stmt = stmt.where(TaskResult.status == status)

        result = await session.execute(stmt)
        return result.scalar_one()

    async def delete_result(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> bool:
        """
        SPEC-HISTORY-001: task_id로 레코드 삭제 (REQ-HIST-007)

        Args:
            session: 비동기 DB 세션
            task_id: 삭제할 작업 ID

        Returns:
            삭제 성공 여부 (True: 삭제됨, False: 존재하지 않음)
        """
        # 단일 DELETE 쿼리로 삭제 - rowcount로 성공 여부 판단
        stmt = delete(TaskResult).where(TaskResult.task_id == task_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
