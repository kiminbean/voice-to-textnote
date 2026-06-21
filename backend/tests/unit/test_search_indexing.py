"""
검색 자동 인덱싱 테스트 - SPEC-SEARCH-001

테스트 범위:
- persist_task_result() 호출 후 검색 인덱스 자동 업데이트
- minutes, summary 타입만 인덱싱
- 인덱싱 실패가 persist에 영향을 주지 않아야 함
"""

from unittest.mock import patch

import pytest


class TestPersistTaskResultIndexing:
    """persist_task_result 호출 시 검색 인덱스 자동 업데이트 테스트"""

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

        self.engine = engine
        yield engine

        # 정리
        engine.dispose()
        sync_engine_module._sync_engine = None
        sync_engine_module._SessionLocal = None

    def test_persist_task_result_indexes_minutes(self):
        """minutes 작업 완료 시 검색 인덱스에 자동 추가되어야 함"""
        from sqlalchemy import text

        from backend.db.search_models import ensure_search_index_table
        from backend.services.sync_service import persist_task_result

        # FTS5 테이블 생성
        ensure_search_index_table(self.engine)

        minutes_data = {
            "segments": [
                {
                    "speaker_id": "SPEAKER_00",
                    "speaker_name": "김팀장",
                    "text": "프로젝트 검색 기능 구현을 논의했습니다.",
                    "start": 0.0,
                    "end": 5.0,
                }
            ],
            "speakers": [{"speaker_id": "SPEAKER_00", "speaker_name": "김팀장"}],
            "total_duration": 300.0,
            "total_speakers": 1,
            "markdown": "# 회의록",
            "created_at": "2024-01-01T09:00:00",
            "completed_at": "2024-01-01T09:05:00",
        }

        persist_task_result(
            task_id="idx-min-001",
            task_type="minutes",
            status="completed",
            result_data=minutes_data,
        )

        # 검색 인덱스에 추가되었는지 확인
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT task_id, task_type, content FROM search_index WHERE task_id = 'idx-min-001'"
                )
            )
            row = result.fetchone()

        assert row is not None, "minutes 결과가 검색 인덱스에 추가되어야 함"
        assert row[0] == "idx-min-001"
        assert row[1] == "minutes"
        assert "검색 기능" in row[2]

    def test_persist_task_result_indexes_summary(self):
        """summary 작업 완료 시 검색 인덱스에 자동 추가되어야 함"""
        from sqlalchemy import text

        from backend.db.search_models import ensure_search_index_table
        from backend.services.sync_service import persist_task_result

        ensure_search_index_table(self.engine)

        summary_data = {
            "summary_text": "이번 회의에서 검색 인덱스 자동화를 논의했습니다.",
            "action_items": [
                {
                    "assignee": "개발팀",
                    "task": "FTS5 인덱스 구현",
                    "deadline": "2024-01-10",
                    "priority": "high",
                }
            ],
            "key_decisions": ["SQLite FTS5 사용 결정"],
            "next_steps": ["테스트 작성"],
            "created_at": "2024-01-01T09:00:00",
            "completed_at": "2024-01-01T09:05:00",
        }

        persist_task_result(
            task_id="idx-sum-001",
            task_type="summary",
            status="completed",
            result_data=summary_data,
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT task_id, task_type, summary_text FROM search_index WHERE task_id = 'idx-sum-001'"
                )
            )
            row = result.fetchone()

        assert row is not None, "summary 결과가 검색 인덱스에 추가되어야 함"
        assert row[0] == "idx-sum-001"
        assert row[1] == "summary"
        assert "검색 인덱스" in row[2]

    def test_persist_task_result_indexes_summary_study_pack(self):
        """summary payload의 Study Pack 텍스트도 검색 인덱스에 포함되어야 함"""
        from sqlalchemy import text

        from backend.db.search_models import ensure_search_index_table
        from backend.services.sync_service import persist_task_result

        ensure_search_index_table(self.engine)

        summary_data = {
            "summary_text": "회의 요약",
            "study_pack": {
                "study_notes": "광합성 복습 노트",
                "key_concepts": [{"term": "엽록체", "explanation": "광합성이 일어나는 장소"}],
                "flashcards": [{"front": "엽록체의 역할은?", "back": "광합성 장소"}],
                "quiz_questions": [
                    {
                        "question": "광합성의 핵심 장소는?",
                        "answer": "엽록체",
                        "difficulty": "easy",
                    }
                ],
            },
            "created_at": "2024-01-01T09:00:00",
            "completed_at": "2024-01-01T09:05:00",
        }

        persist_task_result(
            task_id="idx-sum-study-001",
            task_type="summary",
            status="completed",
            result_data=summary_data,
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT summary_text, action_items_text FROM search_index "
                    "WHERE task_id = 'idx-sum-study-001'"
                )
            )
            row = result.fetchone()

        assert row is not None
        assert "광합성 복습 노트" in row[0]
        assert "엽록체" in row[1]
        assert "광합성의 핵심 장소" in row[1]

    def test_extract_study_pack_terms_skips_non_dict_items(self):
        """Study Pack 검색어 추출은 잘못된 항목을 무시해야 함"""
        from backend.db.search_models import _extract_study_pack_terms

        terms = _extract_study_pack_terms(
            {
                "key_concepts": ["bad", {"term": "개념", "explanation": ""}],
                "flashcards": ["bad", {"front": "질문", "back": ""}],
                "quiz_questions": ["bad", {"question": "문제", "answer": ""}],
            }
        )

        assert terms == ["개념", "질문", "문제"]

    def test_persist_task_result_skips_transcription(self):
        """transcription 작업은 검색 인덱스에 추가되지 않아야 함"""
        from sqlalchemy import text

        from backend.db.search_models import ensure_search_index_table
        from backend.services.sync_service import persist_task_result

        ensure_search_index_table(self.engine)

        persist_task_result(
            task_id="idx-trans-001",
            task_type="transcription",
            status="completed",
            result_data={"text": "안녕하세요 전사 결과입니다."},
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'idx-trans-001'")
            )
            count = result.scalar()

        assert count == 0, "transcription은 검색 인덱스에 추가되지 않아야 함"

    def test_persist_task_result_skips_diarization(self):
        """diarization 작업은 검색 인덱스에 추가되지 않아야 함"""
        from sqlalchemy import text

        from backend.db.search_models import ensure_search_index_table
        from backend.services.sync_service import persist_task_result

        ensure_search_index_table(self.engine)

        persist_task_result(
            task_id="idx-dia-001",
            task_type="diarization",
            status="completed",
            result_data={"speakers": []},
        )

        with self.engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM search_index WHERE task_id = 'idx-dia-001'")
            )
            count = result.scalar()

        assert count == 0, "diarization은 검색 인덱스에 추가되지 않아야 함"

    def test_persist_indexing_failure_doesnt_affect_persist(self):
        """인덱싱 실패가 persist_task_result 동작에 영향을 주면 안 됨"""
        from sqlalchemy import select

        from backend.db.models import TaskResult
        from backend.db.sync_engine import get_sync_session
        from backend.services.sync_service import persist_task_result

        # _try_index_search_entry를 실패하도록 패치
        with patch("backend.services.sync_service._try_index_search_entry") as mock_idx:
            mock_idx.side_effect = Exception("인덱싱 실패")

            # persist는 정상 동작해야 함
            persist_task_result(
                task_id="idx-fail-001",
                task_type="minutes",
                status="completed",
                result_data={"markdown": "# 테스트"},
            )

        # DB에 저장되었는지 확인
        with get_sync_session() as session:
            stmt = select(TaskResult).where(TaskResult.task_id == "idx-fail-001")
            record = session.execute(stmt).scalar_one_or_none()

        assert record is not None, "인덱싱 실패 시에도 DB에 저장되어야 함"
        assert record.status == "completed"

    def test_persist_indexing_failure_is_silent(self):
        """인덱싱 실패는 예외를 전파하지 않고 경고만 로그해야 함"""
        from backend.services.sync_service import persist_task_result

        # _try_index_search_entry가 예외를 throw해도 persist는 성공해야 함
        with patch("backend.services.sync_service._try_index_search_entry") as mock_idx:
            mock_idx.side_effect = RuntimeError("알 수 없는 오류")

            # 예외가 전파되지 않아야 함
            persist_task_result(
                task_id="idx-silent-001",
                task_type="summary",
                status="completed",
                result_data={"summary_text": "테스트 요약"},
            )
            # 여기까지 도달하면 성공
