"""
동기 DB 서비스 테스트 - SPEC-PERSIST-001

테스트 범위:
- REQ-PERSIST-001: Celery 워커용 동기 DB 세션 팩토리
- REQ-PERSIST-002: persist_task_result() 동기 메서드
- REQ-PERSIST-003: DB 저장 실패 시 예외 전파 금지
"""

from unittest.mock import MagicMock, patch

import pytest


class TestGetSyncSession:
    """REQ-PERSIST-001: 동기 DB 세션 팩토리 테스트"""

    def test_get_sync_session_returns_context_manager(self):
        """get_sync_session()이 컨텍스트 매니저를 반환해야 함"""
        from backend.db.sync_engine import get_sync_session

        ctx = get_sync_session()
        # __enter__, __exit__ 속성 확인
        assert hasattr(ctx, "__enter__")
        assert hasattr(ctx, "__exit__")

    def test_sync_session_can_be_used_with_statement(self):
        """with 구문으로 세션을 획득할 수 있어야 함"""
        from backend.db.sync_engine import get_sync_session

        with get_sync_session() as session:
            # 세션 객체가 None이 아님
            assert session is not None

    def test_module_level_engine_can_be_reset(self):
        """테스트 격리를 위해 모듈 수준 엔진을 재설정할 수 있어야 함"""
        import backend.db.sync_engine as sync_engine_module

        # 초기화 전 상태 저장
        original_engine = sync_engine_module._sync_engine

        # 엔진 초기화 (테스트 격리 목적)
        sync_engine_module._sync_engine = None
        sync_engine_module._SessionLocal = None

        # 재설정 후에도 정상 동작 확인
        with sync_engine_module.get_sync_session() as session:
            assert session is not None

        # 복원
        sync_engine_module._sync_engine = original_engine

    def test_async_url_converted_to_sync(self):
        """비동기 URL(+aiosqlite)이 동기 URL로 변환되어야 함"""
        import backend.db.sync_engine as sync_engine_module

        # 엔진 재설정
        sync_engine_module._sync_engine = None
        sync_engine_module._SessionLocal = None

        # aiosqlite URL이 포함된 설정을 모킹
        with patch("backend.db.sync_engine.settings") as mock_settings:
            mock_settings.database_url = "sqlite+aiosqlite:///./test.db"

            # 세션 팩토리 호출 (내부에서 URL 변환 발생)
            engine, _ = sync_engine_module._get_sync_engine()

            # 변환된 URL 확인 (aiosqlite 제거됨)
            assert "aiosqlite" not in str(engine.url)

        # 정리
        sync_engine_module._sync_engine = None
        sync_engine_module._SessionLocal = None


class TestPersistTaskResult:
    """REQ-PERSIST-002: persist_task_result() 기능 테스트"""

    @pytest.fixture(autouse=True)
    def setup_in_memory_db(self):
        """각 테스트마다 인메모리 SQLite DB 세팅"""
        from sqlalchemy import create_engine as sa_create_engine
        from sqlalchemy.orm import sessionmaker

        import backend.db.sync_engine as sync_engine_module
        from backend.db.models import Base

        # 인메모리 SQLite 엔진
        engine = sa_create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session_local = sessionmaker(engine)

        # 모듈 수준 변수를 테스트용으로 교체
        sync_engine_module._sync_engine = engine
        sync_engine_module._SessionLocal = session_local

        yield engine

        # 정리
        engine.dispose()
        sync_engine_module._sync_engine = None
        sync_engine_module._SessionLocal = None

    def test_persist_task_result_saves_completed(self):
        """completed 상태의 결과가 DB에 저장되어야 함"""
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session
        from backend.services.sync_service import persist_task_result

        task_id = "persist-test-001"
        result_data = {"segments": [{"text": "안녕하세요", "start": 0.0, "end": 2.0}]}

        persist_task_result(
            task_id=task_id,
            task_type="transcription",
            status="completed",
            result_data=result_data,
        )

        # DB에서 직접 조회하여 저장 확인
        with get_sync_session() as session:
            stmt = select(TaskResult).where(TaskResult.task_id == task_id)
            record = session.execute(stmt).scalar_one_or_none()

        assert record is not None
        assert record.task_id == task_id
        assert record.task_type == "transcription"
        assert record.status == "completed"
        assert record.result_data == result_data

    def test_persist_task_result_saves_failed(self):
        """failed 상태와 에러 메시지가 DB에 저장되어야 함"""
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session
        from backend.services.sync_service import persist_task_result

        task_id = "persist-test-002"
        error_msg = "오디오 파일 없음"

        persist_task_result(
            task_id=task_id,
            task_type="diarization",
            status="failed",
            error_message=error_msg,
        )

        with get_sync_session() as session:
            stmt = select(TaskResult).where(TaskResult.task_id == task_id)
            record = session.execute(stmt).scalar_one_or_none()

        assert record is not None
        assert record.status == "failed"
        assert record.error_message == error_msg
        assert record.result_data is None

    def test_persist_task_result_upserts_existing(self):
        """동일 task_id로 두 번 호출 시 업데이트(upsert)가 되어야 함"""
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session
        from backend.services.sync_service import persist_task_result

        task_id = "persist-test-003"

        # 첫 번째 저장 (processing 상태)
        persist_task_result(
            task_id=task_id,
            task_type="summary",
            status="processing",
        )

        # 두 번째 저장 (completed 상태로 업데이트)
        persist_task_result(
            task_id=task_id,
            task_type="summary",
            status="completed",
            result_data={"summary_text": "요약 완료"},
        )

        with get_sync_session() as session:
            stmt = select(TaskResult).where(TaskResult.task_id == task_id)
            records = session.execute(stmt).scalars().all()

        # 레코드가 하나만 존재해야 함 (upsert)
        assert len(records) == 1
        assert records[0].status == "completed"
        assert records[0].result_data == {"summary_text": "요약 완료"}

    def test_persist_task_result_all_task_types(self):
        """모든 작업 유형(transcription, diarization, minutes, summary)이 저장 가능해야 함"""
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session
        from backend.services.sync_service import persist_task_result

        task_types = ["transcription", "diarization", "minutes", "summary"]

        for i, task_type in enumerate(task_types):
            persist_task_result(
                task_id=f"persist-type-test-{i:03d}",
                task_type=task_type,
                status="completed",
                result_data={"type": task_type},
            )

        with get_sync_session() as session:
            stmt = select(TaskResult)
            records = session.execute(stmt).scalars().all()

        assert len(records) == 4
        saved_types = {r.task_type for r in records}
        assert saved_types == set(task_types)


class TestPersistTaskResultErrorHandling:
    """REQ-PERSIST-003: DB 저장 실패 시 예외 전파 금지 테스트"""

    def test_db_failure_does_not_raise_exception(self):
        """DB 연결 실패 시 예외가 발생하지 않아야 함 (best-effort)"""
        from backend.services.sync_service import persist_task_result

        # get_sync_session을 실패하도록 모킹
        with patch("backend.services.sync_service.get_sync_session") as mock_session:
            mock_session.side_effect = Exception("DB 연결 실패")

            # 예외가 전파되지 않아야 함
            persist_task_result(
                task_id="error-test-001",
                task_type="transcription",
                status="completed",
                result_data={"data": "test"},
            )
            # 여기까지 도달해야 성공

    def test_session_commit_failure_does_not_raise(self):
        """세션 커밋 실패 시 예외가 발생하지 않아야 함"""
        from backend.services.sync_service import persist_task_result

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.commit.side_effect = Exception("커밋 실패")
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch("backend.services.sync_service.get_sync_session", return_value=mock_session):
            # 예외가 전파되지 않아야 함
            persist_task_result(
                task_id="commit-error-test",
                task_type="minutes",
                status="failed",
            )
            # 여기까지 도달해야 성공

    def test_return_value_is_none_on_success(self):
        """persist_task_result()는 반환값이 없어야 함 (None)"""
        from sqlalchemy import create_engine as sa_create_engine
        from sqlalchemy.orm import sessionmaker

        import backend.db.sync_engine as sync_engine_module
        from backend.db.models import Base
        from backend.services.sync_service import persist_task_result

        engine = sa_create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session_local = sessionmaker(engine)

        sync_engine_module._sync_engine = engine
        sync_engine_module._SessionLocal = session_local

        try:
            result = persist_task_result(
                task_id="return-test-001",
                task_type="transcription",
                status="completed",
            )
            assert result is None
        finally:
            engine.dispose()
            sync_engine_module._sync_engine = None
            sync_engine_module._SessionLocal = None
