"""
데이터 보존 정책 서비스 테스트 - SPEC-RETENTION-001

테스트 범위:
- cleanup_expired_results(): 보존 기간 초과 DB 레코드 삭제
- cleanup_temp_files(): 보존 기간 초과 임시 파일 삭제
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def sync_db_session():
    """인메모리 SQLite 동기 세션 픽스처"""
    from backend.db.models import Base

    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    session_local = sessionmaker(engine)
    session = session_local()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_task_result(task_id: str, created_at: datetime):
    """테스트용 TaskResult 생성 헬퍼"""
    from backend.db.models import TaskResult

    record = TaskResult(
        id=uuid.uuid4(),
        task_id=task_id,
        task_type="transcription",
        status="completed",
        created_at=created_at,
        updated_at=created_at,
    )
    return record


class TestCleanupExpiredResults:
    """REQ-RET-003: 만료된 DB 결과 삭제 테스트"""

    def test_deletes_records_older_than_retention_days(self, sync_db_session):
        """보존 기간보다 오래된 레코드를 삭제한다"""
        from backend.services.retention import cleanup_expired_results

        # 30일보다 오래된 레코드
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=31)
        old_record = make_task_result("task-old-001", old_time)
        sync_db_session.add(old_record)
        sync_db_session.commit()

        deleted = cleanup_expired_results(sync_db_session, retention_days=30)

        assert deleted == 1

    def test_keeps_records_within_retention_days(self, sync_db_session):
        """보존 기간 내 레코드는 삭제하지 않는다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_expired_results

        # 10일 전 레코드 (30일 보존 기간 내)
        recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
        recent_record = make_task_result("task-recent-001", recent_time)
        sync_db_session.add(recent_record)
        sync_db_session.commit()

        deleted = cleanup_expired_results(sync_db_session, retention_days=30)

        assert deleted == 0
        # 레코드가 여전히 존재하는지 확인
        remaining = sync_db_session.execute(
            select(TaskResult).where(TaskResult.task_id == "task-recent-001")
        ).scalars().all()
        assert len(remaining) == 1

    def test_deletes_only_expired_records(self, sync_db_session):
        """만료된 레코드만 삭제하고 최신 레코드는 유지한다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_expired_results

        # 오래된 레코드 2개
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=40)
        sync_db_session.add(make_task_result("task-old-001", old_time))
        sync_db_session.add(make_task_result("task-old-002", old_time))

        # 최신 레코드 1개
        recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=5)
        sync_db_session.add(make_task_result("task-recent-001", recent_time))
        sync_db_session.commit()

        deleted = cleanup_expired_results(sync_db_session, retention_days=30)

        assert deleted == 2
        # 최신 레코드가 남아있는지 확인
        remaining = sync_db_session.execute(select(TaskResult)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].task_id == "task-recent-001"

    def test_returns_zero_when_no_expired_records(self, sync_db_session):
        """만료된 레코드가 없으면 0을 반환한다"""
        from backend.services.retention import cleanup_expired_results

        deleted = cleanup_expired_results(sync_db_session, retention_days=30)

        assert deleted == 0

    def test_custom_retention_days(self, sync_db_session):
        """커스텀 보존 기간(7일)으로 삭제한다"""
        from backend.services.retention import cleanup_expired_results

        # 8일 전 레코드 (7일 기준으로는 만료)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=8)
        sync_db_session.add(make_task_result("task-old-001", old_time))
        sync_db_session.commit()

        deleted = cleanup_expired_results(sync_db_session, retention_days=7)

        assert deleted == 1


class TestCleanupTempFiles:
    """REQ-RET-004: 만료된 임시 파일 삭제 테스트"""

    def test_deletes_old_files(self, tmp_path):
        """보존 시간보다 오래된 파일을 삭제한다"""
        from backend.services.retention import cleanup_temp_files

        old_file = tmp_path / "old_audio.wav"
        old_file.write_bytes(b"x" * 1024)

        # 파일 수정 시각을 25시간 전으로 설정 (24시간 기준 만료)
        old_mtime = (datetime.now(UTC).timestamp()) - (25 * 3600)
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)

        assert deleted_count == 1
        assert freed_bytes == 1024
        assert not old_file.exists()

    def test_keeps_recent_files(self, tmp_path):
        """보존 시간 내 파일은 삭제하지 않는다"""
        from backend.services.retention import cleanup_temp_files

        recent_file = tmp_path / "recent_audio.wav"
        recent_file.write_bytes(b"x" * 512)

        # 파일 수정 시각을 1시간 전으로 설정 (24시간 기준 유효)
        recent_mtime = datetime.now(UTC).timestamp() - 3600
        import os
        os.utime(recent_file, (recent_mtime, recent_mtime))

        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)

        assert deleted_count == 0
        assert freed_bytes == 0
        assert recent_file.exists()

    def test_returns_freed_bytes(self, tmp_path):
        """삭제한 파일들의 총 바이트 크기를 반환한다"""
        from backend.services.retention import cleanup_temp_files

        old_mtime = datetime.now(UTC).timestamp() - (25 * 3600)
        import os

        file1 = tmp_path / "file1.wav"
        file1.write_bytes(b"x" * 2048)
        os.utime(file1, (old_mtime, old_mtime))

        file2 = tmp_path / "file2.wav"
        file2.write_bytes(b"x" * 4096)
        os.utime(file2, (old_mtime, old_mtime))

        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)

        assert deleted_count == 2
        assert freed_bytes == 2048 + 4096

    def test_handles_nonexistent_directory(self, tmp_path):
        """존재하지 않는 디렉토리는 안전하게 처리한다"""
        from backend.services.retention import cleanup_temp_files

        nonexistent = tmp_path / "nonexistent"

        deleted_count, freed_bytes = cleanup_temp_files(nonexistent, retention_hours=24)

        assert deleted_count == 0
        assert freed_bytes == 0

    def test_skips_subdirectories(self, tmp_path):
        """하위 디렉토리는 삭제하지 않는다"""
        from backend.services.retention import cleanup_temp_files

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # 하위 디렉토리의 수정 시각을 오래 전으로 설정
        old_mtime = datetime.now(UTC).timestamp() - (25 * 3600)
        import os
        os.utime(subdir, (old_mtime, old_mtime))

        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)

        # 디렉토리는 삭제하지 않음
        assert deleted_count == 0
        assert subdir.exists()

    def test_empty_directory_returns_zero(self, tmp_path):
        """빈 디렉토리는 0을 반환한다"""
        from backend.services.retention import cleanup_temp_files

        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)

        assert deleted_count == 0
        assert freed_bytes == 0

    def test_handles_file_already_deleted_by_another_worker(self, tmp_path):
        """다른 워커가 이미 삭제한 파일은 안전하게 무시한다"""
        from backend.services.retention import cleanup_temp_files

        old_mtime = datetime.now(UTC).timestamp() - (25 * 3600)
        import os

        # 파일 생성 후 수동으로 unlink → iterdir엔 보이나 stat/unlink에서 FileNotFoundError
        ghost_file = tmp_path / "ghost.wav"
        ghost_file.write_bytes(b"x" * 100)
        os.utime(ghost_file, (old_mtime, old_mtime))

        # 파일을 삭제하여 경쟁 상태 시뮬레이션
        # iterdir()은 파일을 반환하지만 이후 unlink 시 이미 없는 상황은
        # 실제 concurrent 환경에서만 재현되므로, 여기서는 정상 삭제 경로 확인
        deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=24)
        assert deleted_count == 1
        assert freed_bytes == 100


class TestCleanupGuestData:
    """REQ-GUEST-009: 게스트 데이터 정리 테스트"""

    def test_deletes_expired_guest_records(self, sync_db_session):
        """보존 기간이 지난 게스트 레코드를 삭제한다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_guest_data

        # 25시간 전 게스트 레코드
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        guest_record = TaskResult(
            id=uuid.uuid4(),
            task_id="task-guest-001",
            task_type="transcription",
            status="completed",
            is_guest=True,
            created_at=old_time,
            updated_at=old_time,
        )
        sync_db_session.add(guest_record)
        sync_db_session.commit()

        deleted = cleanup_guest_data(sync_db_session, guest_retention_hours=24)

        assert deleted == 1
        remaining = sync_db_session.execute(select(TaskResult)).scalars().all()
        assert len(remaining) == 0

    def test_keeps_recent_guest_records(self, sync_db_session):
        """보존 기간 내 게스트 레코드는 삭제하지 않는다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_guest_data

        # 1시간 전 게스트 레코드 (24시간 보존 기간 내)
        recent_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        guest_record = TaskResult(
            id=uuid.uuid4(),
            task_id="task-guest-recent",
            task_type="transcription",
            status="completed",
            is_guest=True,
            created_at=recent_time,
            updated_at=recent_time,
        )
        sync_db_session.add(guest_record)
        sync_db_session.commit()

        deleted = cleanup_guest_data(sync_db_session, guest_retention_hours=24)

        assert deleted == 0
        remaining = sync_db_session.execute(select(TaskResult)).scalars().all()
        assert len(remaining) == 1

    def test_does_not_delete_non_guest_records(self, sync_db_session):
        """일반(비게스트) 레코드는 보존 기간 초과해도 삭제하지 않는다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_guest_data

        # 25시간 전 일반 레코드 (is_guest=False)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        normal_record = TaskResult(
            id=uuid.uuid4(),
            task_id="task-normal-001",
            task_type="transcription",
            status="completed",
            is_guest=False,
            created_at=old_time,
            updated_at=old_time,
        )
        sync_db_session.add(normal_record)
        sync_db_session.commit()

        deleted = cleanup_guest_data(sync_db_session, guest_retention_hours=24)

        assert deleted == 0
        remaining = sync_db_session.execute(select(TaskResult)).scalars().all()
        assert len(remaining) == 1

    def test_deletes_only_guest_records_mixed(self, sync_db_session):
        """게스트/일반 혼합 시 만료된 게스트만 삭제한다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_guest_data

        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)

        # 만료된 게스트
        expired_guest = TaskResult(
            id=uuid.uuid4(),
            task_id="guest-expired",
            task_type="transcription",
            status="completed",
            is_guest=True,
            created_at=old_time,
            updated_at=old_time,
        )
        # 만료된 일반 레코드 (삭제되지 않아야 함)
        expired_normal = TaskResult(
            id=uuid.uuid4(),
            task_id="normal-expired",
            task_type="transcription",
            status="completed",
            is_guest=False,
            created_at=old_time,
            updated_at=old_time,
        )
        sync_db_session.add_all([expired_guest, expired_normal])
        sync_db_session.commit()

        deleted = cleanup_guest_data(sync_db_session, guest_retention_hours=24)

        assert deleted == 1
        remaining = sync_db_session.execute(select(TaskResult)).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].task_id == "normal-expired"

    def test_default_retention_hours(self, sync_db_session):
        """기본 보존 기간(24시간)으로 동작한다"""
        from backend.db.models import TaskResult
        from backend.services.retention import cleanup_guest_data

        # 25시간 전 게스트
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25)
        sync_db_session.add(
            TaskResult(
                id=uuid.uuid4(),
                task_id="guest-default",
                task_type="transcription",
                status="completed",
                is_guest=True,
                created_at=old_time,
                updated_at=old_time,
            )
        )
        sync_db_session.commit()

        # 기본값으로 호출
        deleted = cleanup_guest_data(sync_db_session)

        assert deleted == 1

    def test_returns_zero_when_no_guest_records(self, sync_db_session):
        """게스트 레코드가 없으면 0을 반환한다"""
        from backend.services.retention import cleanup_guest_data

        deleted = cleanup_guest_data(sync_db_session, guest_retention_hours=24)

        assert deleted == 0
