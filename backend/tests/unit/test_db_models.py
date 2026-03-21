"""
DB 모델 테스트 - REQ-DB-004, REQ-DB-005, REQ-DB-006

테스트 범위:
- TaskResult 모델 (task_id, task_type, status, input_metadata, result_data, ...)
- AuditLog 모델 (request_id, method, path, status_code, client_ip, ...)
- UUID 기본 키 및 자동 타임스탬프
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


@pytest_asyncio.fixture
async def db_session():
    """인메모리 SQLite 세션 픽스처"""
    from backend.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()


class TestTaskResultModel:
    """REQ-DB-004: TaskResult 모델 테스트"""

    @pytest.mark.asyncio
    async def test_create_task_result_minimal(self, db_session):
        """최소 필드로 TaskResult 생성"""
        from backend.db.models import TaskResult

        result = TaskResult(
            task_id="task-001",
            task_type="transcription",
            status="pending",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        assert result.id is not None
        assert result.task_id == "task-001"
        assert result.task_type == "transcription"
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_task_result_uuid_primary_key(self, db_session):
        """REQ-DB-006: UUID 기본 키"""
        from backend.db.models import TaskResult

        result = TaskResult(
            task_id="task-uuid-001",
            task_type="transcription",
            status="pending",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        # UUID 형식 검증
        assert isinstance(result.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_task_result_auto_timestamps(self, db_session):
        """REQ-DB-006: 자동 타임스탬프 (created_at, updated_at)"""
        from backend.db.models import TaskResult

        result = TaskResult(
            task_id="task-ts-001",
            task_type="transcription",
            status="pending",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        assert result.created_at is not None
        assert result.updated_at is not None
        assert isinstance(result.created_at, datetime)
        assert isinstance(result.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_task_result_with_json_fields(self, db_session):
        """JSON 필드 저장 (input_metadata, result_data)"""
        from backend.db.models import TaskResult

        input_meta = {"filename": "test.mp3", "duration": 120}
        result_data = {"transcript": "안녕하세요", "confidence": 0.95}

        result = TaskResult(
            task_id="task-json-001",
            task_type="transcription",
            status="completed",
            input_metadata=input_meta,
            result_data=result_data,
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        assert result.input_metadata == input_meta
        assert result.result_data == result_data

    @pytest.mark.asyncio
    async def test_task_result_error_message_nullable(self, db_session):
        """error_message 필드 NULL 허용"""
        from backend.db.models import TaskResult

        result = TaskResult(
            task_id="task-null-err-001",
            task_type="transcription",
            status="pending",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_task_result_completed_at_nullable(self, db_session):
        """completed_at 필드 NULL 허용 (미완료 상태)"""
        from backend.db.models import TaskResult

        result = TaskResult(
            task_id="task-no-complete-001",
            task_type="transcription",
            status="processing",
        )
        db_session.add(result)
        await db_session.commit()
        await db_session.refresh(result)

        assert result.completed_at is None

    @pytest.mark.asyncio
    async def test_task_result_task_id_unique(self, db_session):
        """task_id 유니크 인덱스 - 중복 삽입 시 오류"""
        from sqlalchemy.exc import IntegrityError

        from backend.db.models import TaskResult

        result1 = TaskResult(
            task_id="task-dup-001",
            task_type="transcription",
            status="pending",
        )
        result2 = TaskResult(
            task_id="task-dup-001",  # 동일한 task_id
            task_type="transcription",
            status="completed",
        )
        db_session.add(result1)
        await db_session.commit()

        db_session.add(result2)
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestAuditLogModel:
    """REQ-DB-005: AuditLog 모델 테스트"""

    @pytest.mark.asyncio
    async def test_create_audit_log(self, db_session):
        """AuditLog 생성"""
        from backend.db.models import AuditLog

        log = AuditLog(
            request_id="req-001",
            method="POST",
            path="/api/v1/transcriptions",
            status_code=200,
            client_ip="127.0.0.1",
            duration_ms=45.3,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.request_id == "req-001"
        assert log.method == "POST"
        assert log.path == "/api/v1/transcriptions"
        assert log.status_code == 200
        assert log.client_ip == "127.0.0.1"
        assert log.duration_ms == pytest.approx(45.3, abs=0.001)

    @pytest.mark.asyncio
    async def test_audit_log_uuid_primary_key(self, db_session):
        """REQ-DB-006: AuditLog UUID 기본 키"""
        from backend.db.models import AuditLog

        log = AuditLog(
            request_id="req-uuid-001",
            method="GET",
            path="/health",
            status_code=200,
            client_ip="10.0.0.1",
            duration_ms=5.0,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert isinstance(log.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_audit_log_auto_timestamp(self, db_session):
        """AuditLog 자동 timestamp"""
        from backend.db.models import AuditLog

        log = AuditLog(
            request_id="req-ts-001",
            method="GET",
            path="/health",
            status_code=200,
            client_ip="10.0.0.1",
            duration_ms=5.0,
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.timestamp is not None
        assert isinstance(log.timestamp, datetime)
