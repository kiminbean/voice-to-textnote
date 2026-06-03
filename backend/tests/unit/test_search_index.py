"""
SPEC-SEARCH-001: 회의록 전문 검색 FTS5 인덱스 테스트

TDD Red Phase: 실패하는 테스트 먼저 작성
REQ-SEARCH-002: FTS5 인덱스 자동 생성 및 인덱싱 함수 테스트
"""

import uuid

import pytest
from sqlalchemy import create_engine, text


class TestFTS5TableCreation:
    """FTS5 search_index 테이블 생성 검증"""

    def test_ensure_search_index_table_creates_fts5_virtual_table(self, tmp_path):
        """ensure_search_index_table()가 FTS5 virtual table을 생성해야 함"""
        from backend.db.search_models import ensure_search_index_table

        # 임시 SQLite DB 생성
        db_path = tmp_path / "test_search.db"
        engine = create_engine(f"sqlite:///{db_path}")

        # 테이블 생성
        ensure_search_index_table(engine)

        # 테이블 존재 확인
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='search_index'"
                )
            )
            tables = [row[0] for row in result]
            assert "search_index" in tables

    def test_fts5_table_schema_columns(self, tmp_path):
        """FTS5 테이블 스키마가 요구사항을 충족해야 함"""
        from backend.db.search_models import ensure_search_index_table

        db_path = tmp_path / "test_search.db"
        engine = create_engine(f"sqlite:///{db_path}")

        ensure_search_index_table(engine)

        with engine.connect() as conn:
            # PRAGMA table_info로 컬럼 확인
            result = conn.execute(text("PRAGMA table_info(search_index)"))
            columns = {row[1]: row[2] for row in result}

            # 필수 컬럼 확인
            assert "task_id" in columns
            assert "task_type" in columns
            assert "content" in columns
            assert "speaker_names" in columns
            assert "summary_text" in columns
            assert "action_items_text" in columns
            assert "created_at" in columns

    def test_fts5_tokenizer_unicode61(self, tmp_path):
        """FTS5 토크나이저가 unicode61이어야 함 (Korean 지원)"""
        from backend.db.search_models import ensure_search_index_table

        db_path = tmp_path / "test_search.db"
        engine = create_engine(f"sqlite:///{db_path}")

        ensure_search_index_table(engine)

        with engine.connect() as conn:
            # FTS5 테이블 SQL 확인
            result = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE name='search_index'")
            )
            sql = result.scalar()

            # FTS5 및 unicode61 토크나이저 확인
            assert "VIRTUAL TABLE" in sql.upper()
            assert "using fts5" in sql.lower()  # 소문자로 검색
            assert "unicode61" in sql.lower()


class TestIndexSearchEntryMinutes:
    """minutes 결과 데이터 인덱싱 테스트"""

    def test_index_minutes_entry_extracts_content_and_speakers(
        self, tmp_path, get_sync_session
    ):
        """minutes result_data에서 content와 speaker_names를 추출해야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        db_path = tmp_path / "test_minutes.db"
        engine = create_engine(f"sqlite:///{db_path}")
        ensure_search_index_table(engine)

        task_id = str(uuid.uuid4())
        result_data = {
            "segments": [
                {"text": "안녕하세요", "speaker_name": "A"},
                {"text": "반갑습니다", "speaker_name": "B"},
                {"text": "회의를 시작하겠습니다", "speaker_name": "A"},
            ]
        }

        with get_sync_session(engine) as session:
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=result_data,
            )
            session.commit()

        # 인덱싱된 데이터 확인
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT content, speaker_names FROM search_index WHERE task_id=:task_id"),
                {"task_id": task_id},
            )
            row = result.fetchone()

            assert row is not None
            content, speaker_names = row
            assert "안녕하세요" in content
            assert "반갑습니다" in content
            assert "회의를 시작하겠습니다" in content
            # speaker_names는 공백으로 구분된 고유 집합
            speakers_set = set(speaker_names.split())  # 공백으로 분리
            assert "A" in speakers_set
            assert "B" in speakers_set


class TestIndexSearchEntrySummary:
    """summary 결과 데이터 인덱싱 테스트"""

    def test_index_summary_entry_extracts_summary_and_action_items(
        self, tmp_path, get_sync_session
    ):
        """summary result_data에서 summary_text와 action_items_text를 추출해야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        db_path = tmp_path / "test_summary.db"
        engine = create_engine(f"sqlite:///{db_path}")
        ensure_search_index_table(engine)

        task_id = str(uuid.uuid4())
        result_data = {
            "summary_text": "회의에서 프로젝트 일정을 논의했습니다",
            "action_items": [
                {"task": "기획서 작성"},
                {"task": "회의록 공유"},
            ],
            "key_decisions": ["다음주 화요일 회의", "PM 선정"],
            "next_steps": ["이해관계자 동의 확보"],
        }

        with get_sync_session(engine) as session:
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="summary",
                result_data=result_data,
            )
            session.commit()

        # 인덱싱된 데이터 확인
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT summary_text, action_items_text FROM search_index WHERE task_id=:task_id"
                ),
                {"task_id": task_id},
            )
            row = result.fetchone()

            assert row is not None
            summary_text, action_items_text = row
            assert "프로젝트 일정을 논의했습니다" in summary_text
            assert "기획서 작성" in action_items_text
            assert "회의록 공유" in action_items_text
            assert "다음주 화요일 회의" in action_items_text
            assert "PM 선정" in action_items_text
            assert "이해관계자 동의 확보" in action_items_text


class TestIndexSearchEntryUpsert:
    """중복 task_id upsert 테스트"""

    def test_duplicate_task_id_should_update_existing_entry(
        self, tmp_path, get_sync_session
    ):
        """동일 task_id로 재인덱싱 시 기존 레코드를 업데이트해야 함"""
        from backend.db.search_models import ensure_search_index_table, index_search_entry

        db_path = tmp_path / "test_upsert.db"
        engine = create_engine(f"sqlite:///{db_path}")
        ensure_search_index_table(engine)

        task_id = str(uuid.uuid4())

        # 첫 번째 인덱싱
        result_data_v1 = {
            "segments": [
                {"text": "초기 내용", "speaker_name": "A"},
            ]
        }

        with get_sync_session(engine) as session:
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=result_data_v1,
            )
            session.commit()

        # 두 번째 인덱싱 (업데이트)
        result_data_v2 = {
            "segments": [
                {"text": "수정된 내용", "speaker_name": "B"},
            ]
        }

        with get_sync_session(engine) as session:
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=result_data_v2,
            )
            session.commit()

        # 업데이트된 내용 확인
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT content FROM search_index WHERE task_id=:task_id"),
                {"task_id": task_id},
            )
            row = result.fetchone()

            assert row is not None
            content = row[0]
            assert "수정된 내용" in content
            assert "초기 내용" not in content


class TestIndexSearchEntryBestEffort:
    """인덱싱 실패 시 best-effort 처리 테스트"""

    def test_indexing_failure_should_not_raise_exception(
        self, tmp_path, get_sync_session, caplog
    ):
        """인덱싱 실패 시 예외를 전파하지 않고 로그만 남겨야 함"""
        from backend.db.search_models import index_search_entry

        # 유효하지 않은 result_data 구조
        task_id = str(uuid.uuid4())
        result_data = {"invalid": "structure"}  # segments 없음

        with get_sync_session(None) as session:  # Dummy session
            # 예외가 발생하지 않아야 함
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=result_data,
            )

        # 로그에 경고가 기록되었는지 확인 (로거 설정에 따라)
        # 실제 구현에서는 try-except로 감싸서 예외를吞해야 함

    def test_missing_result_data_should_gracefully_skip(self, tmp_path, get_sync_session):
        """result_data가 None이거나 비어있을 때 정상적으로 처리해야 함"""
        from backend.db.search_models import index_search_entry

        task_id = str(uuid.uuid4())

        with get_sync_session(None) as session:
            # None result_data - 예외 없어야 함
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=None,
            )

            # Empty dict - 예외 없어야 함
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="summary",
                result_data={},
            )


class TestDeleteSearchEntry:
    """검색 인덱스 삭제 테스트"""

    def test_delete_search_entry_removes_indexed_record(
        self, tmp_path, get_sync_session
    ):
        """delete_search_entry()가 인덱싱된 레코드를 삭제해야 함"""
        from backend.db.search_models import (
            delete_search_entry,
            ensure_search_index_table,
            index_search_entry,
        )

        db_path = tmp_path / "test_delete.db"
        engine = create_engine(f"sqlite:///{db_path}")
        ensure_search_index_table(engine)

        task_id = str(uuid.uuid4())
        result_data = {
            "segments": [
                {"text": "삭제될 내용", "speaker_name": "A"},
            ]
        }

        # 인덱싱
        with get_sync_session(engine) as session:
            index_search_entry(
                session=session,
                task_id=task_id,
                task_type="minutes",
                result_data=result_data,
            )
            session.commit()

        # 삭제
        with get_sync_session(engine) as session:
            delete_search_entry(session=session, task_id=task_id)
            session.commit()

        # 삭제 확인
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM search_index WHERE task_id=:task_id"),
                {"task_id": task_id},
            )
            count = result.scalar()
            assert count == 0


class TestIndexSearchEntryFiltering:
    """task_type 필터링 테스트"""

    def test_transcription_and_diarization_should_not_be_indexed(
        self, tmp_path, get_sync_session
    ):
        """transcription, diarization 타입은 인덱싱하지 않아야 함"""
        from backend.db.search_models import (
            ensure_search_index_table,
            index_search_entry,
        )

        db_path = tmp_path / "test_filter.db"
        engine = create_engine(f"sqlite:///{db_path}")
        ensure_search_index_table(engine)

        with get_sync_session(engine) as session:
            # transcription - 인덱싱되지 않아야 함
            index_search_entry(
                session=session,
                task_id=str(uuid.uuid4()),
                task_type="transcription",
                result_data={"segments": [{"text": "테스트"}]},
            )

            # diarization - 인덱싱되지 않아야 함
            index_search_entry(
                session=session,
                task_id=str(uuid.uuid4()),
                task_type="diarization",
                result_data={"segments": [{"text": "테스트"}]},
            )

            session.commit()

        # 두 레코드 모두 없어야 함
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM search_index"))
            count = result.scalar()
            assert count == 0


# ---------------------------------------------------------------------------
# 테스트용 sync_session fixture (conftest.py에 있어야 함 but here for standalone)
# ---------------------------------------------------------------------------


@pytest.fixture
def get_sync_session():
    """테스트용 동기 세션 팩토리"""
    from contextlib import contextmanager

    from backend.db.sync_engine import get_sync_session as actual_get_sync_session

    @contextmanager
    def _wrapper(engine=None):
        if engine is not None:
            # 커스텀 엔진 사용 (임시 DB용)
            from sqlalchemy.orm import Session

            with Session(engine) as session:
                yield session
        else:
            # 기본 엔진 사용
            with actual_get_sync_session() as session:
                yield session

    return _wrapper
