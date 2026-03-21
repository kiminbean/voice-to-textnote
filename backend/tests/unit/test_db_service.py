"""
DB 서비스 테스트 - REQ-DB-009, REQ-DB-010, REQ-DB-011

테스트 범위:
- ResultService.save_result(): 결과 DB 저장
- ResultService.get_result(): task_id로 단건 조회
- ResultService.list_results(): 목록 조회 (페이징, 필터)
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_session():
    """인메모리 SQLite 세션 픽스처"""
    from backend.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with session_local() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def result_service():
    """ResultService 인스턴스"""
    from backend.db.service import ResultService

    return ResultService()


class TestSaveResult:
    """REQ-DB-009, REQ-DB-011: save_result() 테스트"""

    @pytest.mark.asyncio
    async def test_save_result_creates_record(self, db_session, result_service):
        """결과를 DB에 저장"""
        record = await result_service.save_result(
            session=db_session,
            task_id="task-save-001",
            task_type="transcription",
            status="completed",
            result_data={"transcript": "안녕하세요"},
            input_metadata={"filename": "audio.mp3"},
        )

        assert record is not None
        assert record.task_id == "task-save-001"
        assert record.task_type == "transcription"
        assert record.status == "completed"
        assert record.result_data == {"transcript": "안녕하세요"}
        assert record.input_metadata == {"filename": "audio.mp3"}

    @pytest.mark.asyncio
    async def test_save_result_with_error_message(self, db_session, result_service):
        """오류 메시지와 함께 저장"""
        record = await result_service.save_result(
            session=db_session,
            task_id="task-err-001",
            task_type="transcription",
            status="failed",
            result_data=None,
            input_metadata=None,
            error_message="파일을 읽을 수 없습니다",
        )

        assert record.status == "failed"
        assert record.error_message == "파일을 읽을 수 없습니다"

    @pytest.mark.asyncio
    async def test_save_result_sets_uuid(self, db_session, result_service):
        """저장된 레코드에 UUID 할당"""
        record = await result_service.save_result(
            session=db_session,
            task_id="task-uuid-save-001",
            task_type="transcription",
            status="pending",
        )

        assert isinstance(record.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_save_result_sets_created_at(self, db_session, result_service):
        """created_at 자동 설정"""
        record = await result_service.save_result(
            session=db_session,
            task_id="task-created-001",
            task_type="transcription",
            status="pending",
        )

        assert record.created_at is not None

    @pytest.mark.asyncio
    async def test_save_result_updates_existing(self, db_session, result_service):
        """동일 task_id로 재저장 시 업데이트 (upsert)"""
        # 최초 저장
        await result_service.save_result(
            session=db_session,
            task_id="task-upsert-001",
            task_type="transcription",
            status="pending",
        )

        # 업데이트
        updated = await result_service.save_result(
            session=db_session,
            task_id="task-upsert-001",
            task_type="transcription",
            status="completed",
            result_data={"transcript": "업데이트됨"},
        )

        assert updated.status == "completed"
        assert updated.result_data == {"transcript": "업데이트됨"}


class TestGetResult:
    """REQ-DB-010, REQ-DB-011: get_result() 테스트"""

    @pytest.mark.asyncio
    async def test_get_result_returns_record(self, db_session, result_service):
        """task_id로 레코드 조회"""
        await result_service.save_result(
            session=db_session,
            task_id="task-get-001",
            task_type="transcription",
            status="completed",
            result_data={"transcript": "테스트"},
        )

        record = await result_service.get_result(
            session=db_session,
            task_id="task-get-001",
        )

        assert record is not None
        assert record.task_id == "task-get-001"
        assert record.result_data == {"transcript": "테스트"}

    @pytest.mark.asyncio
    async def test_get_result_returns_none_when_not_found(
        self, db_session, result_service
    ):
        """존재하지 않는 task_id 조회 시 None 반환 (캐시 미스 폴백 지원)"""
        record = await result_service.get_result(
            session=db_session,
            task_id="nonexistent-task",
        )

        assert record is None

    @pytest.mark.asyncio
    async def test_get_result_after_cache_miss(self, db_session, result_service):
        """REQ-DB-010: Redis 캐시 미스 후 DB 폴백 시나리오"""
        # DB에 직접 저장된 레코드를 get_result로 조회
        await result_service.save_result(
            session=db_session,
            task_id="task-fallback-001",
            task_type="diarization",
            status="completed",
            result_data={"speakers": ["Speaker A", "Speaker B"]},
        )

        # Redis 캐시 없이 DB에서 직접 조회 (폴백 시뮬레이션)
        record = await result_service.get_result(
            session=db_session,
            task_id="task-fallback-001",
        )

        assert record is not None
        assert record.result_data == {"speakers": ["Speaker A", "Speaker B"]}


class TestListResults:
    """REQ-DB-011: list_results() 테스트"""

    @pytest.mark.asyncio
    async def test_list_results_returns_all(self, db_session, result_service):
        """모든 결과 목록 조회"""
        for i in range(3):
            await result_service.save_result(
                session=db_session,
                task_id=f"task-list-{i:03d}",
                task_type="transcription",
                status="completed",
            )

        results = await result_service.list_results(session=db_session)

        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_list_results_filter_by_task_type(self, db_session, result_service):
        """task_type 필터링"""
        await result_service.save_result(
            session=db_session,
            task_id="task-type-filter-001",
            task_type="transcription",
            status="completed",
        )
        await result_service.save_result(
            session=db_session,
            task_id="task-type-filter-002",
            task_type="diarization",
            status="completed",
        )

        transcription_results = await result_service.list_results(
            session=db_session,
            task_type="transcription",
        )

        assert all(r.task_type == "transcription" for r in transcription_results)

    @pytest.mark.asyncio
    async def test_list_results_pagination(self, db_session, result_service):
        """limit/offset 페이징"""
        for i in range(5):
            await result_service.save_result(
                session=db_session,
                task_id=f"task-page-{i:03d}",
                task_type="transcription",
                status="completed",
            )

        page1 = await result_service.list_results(
            session=db_session, limit=2, offset=0
        )
        page2 = await result_service.list_results(
            session=db_session, limit=2, offset=2
        )

        assert len(page1) == 2
        assert len(page2) == 2
        # 페이지 간 중복 없음
        page1_ids = {r.task_id for r in page1}
        page2_ids = {r.task_id for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_list_results_empty_when_no_data(self, db_session, result_service):
        """데이터 없을 때 빈 리스트 반환"""
        results = await result_service.list_results(
            session=db_session,
            task_type="nonexistent_type",
        )

        assert results == []
