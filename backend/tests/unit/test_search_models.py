"""
검색 인덱스 모델 테스트 - SPEC-SEARCH-001

테스트 범위:
- ensure_search_index_table(): FTS5 가상 테이블 생성
- index_search_entry(): 검색 인덱스 항목 추가/갱신
- delete_search_entry(): 검색 인덱스 항목 삭제
"""

import pytest
from sqlalchemy import create_engine, text

from backend.db.models import Base

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_engine():
    """인메모리 SQLite 동기 엔진 픽스처"""
    engine = create_engine("sqlite://", echo=False)
    with engine.begin() as conn:
        # ORM 테이블 생성 (task_results 등)
        Base.metadata.create_all(conn)
    yield engine
    engine.dispose()


@pytest.fixture
def sync_session(sync_engine):
    """동기 세션 픽스처"""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(sync_engine)
    session = Session()
    yield session
    session.close()


# 샘플 minutes result_data
SAMPLE_MINUTES = {
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "김팀장",
            "text": "오늘 회의를 시작하겠습니다. 안건을 검토해 봅시다.",
            "start": 0.0,
            "end": 5.0,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "이개발",
            "text": "네, 말씀하신 대로 진행하겠습니다.",
            "start": 5.0,
            "end": 9.0,
        },
    ],
    "speakers": [
        {"speaker_id": "SPEAKER_00", "speaker_name": "김팀장"},
        {"speaker_id": "SPEAKER_01", "speaker_name": "이개발"},
    ],
    "total_duration": 300.0,
    "total_speakers": 2,
    "markdown": "# 회의록",
    "created_at": "2024-01-01T09:00:00",
    "completed_at": "2024-01-01T09:05:00",
}

# 샘플 summary result_data
SAMPLE_SUMMARY = {
    "summary_text": "이번 회의에서 프로젝트 일정 및 기술 스택을 논의했습니다.",
    "action_items": [
        {
            "assignee": "김팀장",
            "task": "보고서 작성 완료",
            "deadline": "2024-01-05",
            "priority": "high",
        },
        {
            "assignee": "이개발",
            "task": "API 개발 시작",
            "deadline": "2024-01-10",
            "priority": "medium",
        },
    ],
    "key_decisions": ["FastAPI 사용 결정", "SQLite 프로토타입 후 PostgreSQL 전환"],
    "next_steps": ["다음 주 스프린트 계획 수립"],
    "created_at": "2024-01-01T09:10:00",
    "completed_at": "2024-01-01T09:15:00",
}


# ---------------------------------------------------------------------------
# Phase 1 테스트: ensure_search_index_table
# ---------------------------------------------------------------------------


class TestEnsureSearchIndexTable:
    """FTS5 가상 테이블 생성 테스트"""

    def test_ensure_search_index_table_creates_table(self, sync_engine):
        """FTS5 search_index 테이블이 생성되어야 함"""
        from backend.db.search_models import ensure_search_index_table

        ensure_search_index_table(sync_engine)

        # 테이블 존재 확인
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'")
            )
            row = result.fetchone()
        assert row is not None, "search_index 테이블이 생성되어야 함"

    def test_ensure_search_index_table_idempotent(self, sync_engine):
        """여러 번 호출해도 오류 없이 실행되어야 함 (IF NOT EXISTS)"""
        from backend.db.search_models import ensure_search_index_table

        # 두 번 호출해도 예외 없음
        ensure_search_index_table(sync_engine)
        ensure_search_index_table(sync_engine)

    def test_ensure_search_index_table_with_connection(self, sync_engine):
        """Connection 객체로도 동작해야 함"""
        from backend.db.search_models import ensure_search_index_table

        with sync_engine.connect() as conn:
            ensure_search_index_table(conn)
            # 커밋 없이도 테이블 존재 확인 가능
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'")
            )
            row = result.fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Phase 2 테스트: index_search_entry
# ---------------------------------------------------------------------------


class TestIndexSearchEntry:
    """검색 인덱스 항목 추가/갱신 테스트"""

    def test_index_search_entry_minutes(self, sync_engine, sync_session):
        """minutes 결과를 검색 인덱스에 추가해야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        ensure_search_index_table(sync_engine)
        index_search_entry(
            session=sync_session,
            task_id="task-min-001",
            task_type="minutes",
            result_data=SAMPLE_MINUTES,
        )
        sync_session.commit()

        # 인덱스 항목 존재 확인
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT task_id, task_type, content, speaker_names FROM search_index WHERE task_id = 'task-min-001'")
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "task-min-001"
        assert row[1] == "minutes"
        # content에 segments의 텍스트가 포함되어야 함
        assert "오늘 회의를 시작하겠습니다" in row[2]
        # speaker_names에 화자 이름이 포함되어야 함
        assert "김팀장" in row[3]
        assert "이개발" in row[3]

    def test_index_search_entry_summary(self, sync_engine, sync_session):
        """summary 결과를 검색 인덱스에 추가해야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        ensure_search_index_table(sync_engine)
        index_search_entry(
            session=sync_session,
            task_id="task-sum-001",
            task_type="summary",
            result_data=SAMPLE_SUMMARY,
        )
        sync_session.commit()

        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT task_id, task_type, summary_text, action_items_text FROM search_index WHERE task_id = 'task-sum-001'")
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == "task-sum-001"
        assert row[1] == "summary"
        # summary_text 포함 확인
        assert "프로젝트 일정" in row[2]
        # action_items_text에 action item task 텍스트가 포함되어야 함
        assert "보고서 작성" in row[3]

    def test_index_search_entry_upsert(self, sync_engine, sync_session):
        """같은 task_id로 두 번 추가하면 업데이트되어야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        ensure_search_index_table(sync_engine)

        # 첫 번째 추가
        index_search_entry(
            session=sync_session,
            task_id="task-upsert-001",
            task_type="minutes",
            result_data=SAMPLE_MINUTES,
        )
        sync_session.commit()

        # 수정된 데이터로 두 번째 추가
        modified_minutes = {**SAMPLE_MINUTES, "segments": [
            {
                "speaker_id": "SPEAKER_00",
                "speaker_name": "박차장",
                "text": "업데이트된 내용입니다.",
                "start": 0.0,
                "end": 3.0,
            }
        ]}
        index_search_entry(
            session=sync_session,
            task_id="task-upsert-001",
            task_type="minutes",
            result_data=modified_minutes,
        )
        sync_session.commit()

        # 하나의 항목만 존재해야 함
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'task-upsert-001'")
            )
            count = result.scalar()
        assert count == 1

        # 내용이 업데이트되어야 함
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT content FROM search_index WHERE task_id = 'task-upsert-001'")
            )
            row = result.fetchone()
        assert "업데이트된 내용입니다" in row[0]

    def test_index_search_entry_skips_transcription(self, sync_engine, sync_session):
        """transcription 타입은 인덱싱하지 않아야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        ensure_search_index_table(sync_engine)
        index_search_entry(
            session=sync_session,
            task_id="task-trans-001",
            task_type="transcription",
            result_data={"text": "안녕하세요"},
        )
        sync_session.commit()

        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'task-trans-001'")
            )
            count = result.scalar()
        assert count == 0, "transcription은 인덱싱하지 않아야 함"

    def test_index_search_entry_skips_diarization(self, sync_engine, sync_session):
        """diarization 타입은 인덱싱하지 않아야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        ensure_search_index_table(sync_engine)
        index_search_entry(
            session=sync_session,
            task_id="task-dia-001",
            task_type="diarization",
            result_data={"speakers": []},
        )
        sync_session.commit()

        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'task-dia-001'")
            )
            count = result.scalar()
        assert count == 0, "diarization은 인덱싱하지 않아야 함"

    def test_index_search_entry_error_handling(self, sync_session):
        """예외가 발생해도 re-raise하지 않아야 함 (best-effort)"""
        from backend.db.search_models import index_search_entry

        # FTS5 테이블이 없는 상태에서 호출 (오류 발생하더라도 무시)
        # 예외가 전파되지 않아야 함
        index_search_entry(
            session=sync_session,
            task_id="task-err-001",
            task_type="minutes",
            result_data=SAMPLE_MINUTES,
        )
        # 여기까지 도달하면 예외가 전파되지 않음을 증명


# ---------------------------------------------------------------------------
# Phase 3 테스트: delete_search_entry
# ---------------------------------------------------------------------------


class TestDeleteSearchEntry:
    """검색 인덱스 항목 삭제 테스트"""

    def test_delete_search_entry(self, sync_engine, sync_session):
        """task_id로 검색 인덱스 항목을 삭제해야 함"""
        from backend.db.search_models import (
            delete_search_entry,
            ensure_search_index_table,
            index_search_entry,
        )

        ensure_search_index_table(sync_engine)

        # 먼저 추가
        index_search_entry(
            session=sync_session,
            task_id="task-del-001",
            task_type="minutes",
            result_data=SAMPLE_MINUTES,
        )
        sync_session.commit()

        # 삭제
        delete_search_entry(sync_session, "task-del-001")
        sync_session.commit()

        # 삭제 확인
        with sync_engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'task-del-001'")
            )
            count = result.scalar()
        assert count == 0

    def test_delete_search_entry_nonexistent(self, sync_engine, sync_session):
        """존재하지 않는 항목 삭제 시 오류 없어야 함"""
        from backend.db.search_models import delete_search_entry, ensure_search_index_table

        ensure_search_index_table(sync_engine)

        # 존재하지 않는 항목 삭제 - 예외 없어야 함
        delete_search_entry(sync_session, "nonexistent-task-id")
        sync_session.commit()
