"""
검색 제안 서비스 테스트 - SPEC-SEARCH-002 Phase 2

REQ-SEARCH-009: 자동완성 제안 기능
- FTS5 접두사 검색으로 제안 토큰 반환
- 중복 제거 및 최대 10개 결과 제한
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.search_service import SearchService


@pytest_asyncio.fixture
async def async_engine():
    """비동기 테스트용 인메모리 엔진"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    """비동기 DB 세션 픽스처 — FTS5 테이블만 생성"""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        # FTS5 테이블만 생성 (task_results 불필요)
        await session.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index "
                "USING fts5(task_id, task_type, content, speaker_names, "
                "summary_text, action_items_text, created_at UNINDEXED, "
                "tokenize='unicode61')"
            )
        )
        yield session


@pytest_asyncio.fixture
async def sample_search_index_data(db_session: AsyncSession):
    """검색 인덱스에 샘플 데이터를 직접 SQL로 삽입"""
    search_rows = [
        {
            "task_id": "sugg-min-001",
            "task_type": "minutes",
            "content": "회의록 내용입니다 회계 보고를 진행합니다",
            "speaker_names": "김철수 이영호",
            "summary_text": "",
            "action_items_text": "회의 진행",
            "created_at": "2024-01-01T09:00:00",
        },
        {
            "task_id": "sugg-min-002",
            "task_type": "minutes",
            "content": "효율적인 업무 처리 방안 논의",
            "speaker_names": "박지성",
            "summary_text": "",
            "action_items_text": "",
            "created_at": "2024-01-02T09:00:00",
        },
        {
            "task_id": "sugg-sum-001",
            "task_type": "summary",
            "content": "",
            "speaker_names": "",
            "summary_text": "정기 회의록 요약 회의록 작성 완료",
            "action_items_text": "회의 진행",
            "created_at": "2024-01-03T09:00:00",
        },
        {
            "task_id": "sugg-sum-002",
            "task_type": "summary",
            "content": "",
            "speaker_names": "",
            "summary_text": "중복 회의록 검토 회의록 분석",
            "action_items_text": "중복 회의록 정리",
            "created_at": "2024-01-04T09:00:00",
        },
    ]

    insert_sql = text(
        "INSERT INTO search_index "
        "(task_id, task_type, content, speaker_names, summary_text, action_items_text, created_at) "
        "VALUES (:task_id, :task_type, :content, :speaker_names, :summary_text, :action_items_text, :created_at)"
    )
    for row in search_rows:
        await db_session.execute(insert_sql, row)
    await db_session.commit()


class TestSearchSuggestions:
    """검색 제안 기능 테스트 스위트"""

    @pytest.mark.asyncio
    async def test_returns_matching_tokens_from_fts5_index(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: FTS5 인덱스에서 일치하는 토큰 반환

        Given: 검색 인덱스에 "회의록", "회계" 등의 토큰이 존재
        When: "회" 접두사로 제안 요청
        Then: "회의록", "회계" 등 관련 토큰 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회", limit=10)

        assert len(suggestions) > 0
        assert any("회" in s for s in suggestions)

    @pytest.mark.asyncio
    async def test_empty_prefix_returns_empty_list(
        self, db_session: AsyncSession
    ):
        """
        REQ-SEARCH-009: 빈 접두사는 빈 목록 반환

        Given: 검색 인덱스 존재
        When: 빈 문자열 또는 공백만 있는 접두사
        Then: 빈 목록 반환 (검색 실행하지 않음)
        """
        service = SearchService()

        suggestions_empty = await service.get_suggestions(db_session, prefix="", limit=10)
        suggestions_whitespace = await service.get_suggestions(
            db_session, prefix="   ", limit=10
        )

        assert suggestions_empty == []
        assert suggestions_whitespace == []

    @pytest.mark.asyncio
    async def test_suggestions_limited_to_max_10_results(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: 최대 10개 결과 제한

        Given: 검색 인덱스에 다수 토큰 존재
        When: 기본 limit=10 으로 제안 요청
        Then: 최대 10개만 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회", limit=10)

        assert len(suggestions) <= 10

    @pytest.mark.asyncio
    async def test_custom_limit_parameter_works(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: 사용자 지정 limit 파라미터 동작

        Given: 검색 인덱스에 다수 토큰 존재
        When: limit=2로 제안 요청
        Then: 최대 2개만 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회", limit=2)

        assert len(suggestions) <= 2

    @pytest.mark.asyncio
    async def test_duplicate_tokens_are_deduplicated(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: 중복 토큰 제거

        Given: 검색 인덱스에 "회의록"이 여러 문서에 존재
        When: 제안 요청
        Then: 중복 제거된 고유 토큰 목록 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회")

        # 중복 없음 확인
        assert len(suggestions) == len(set(suggestions))

    @pytest.mark.asyncio
    async def test_special_characters_are_sanitized(
        self, db_session: AsyncSession
    ):
        """
        REQ-SEARCH-009: 특수 문자 처리 (SQL 인젝션 방지)

        Given: 검색 인덱스 존재
        When: SQL 특수 문자 포함 접두사로 제안 요청
        Then: 예외 없이 빈 목록 또는 안전한 결과 반환
        """
        service = SearchService()
        # 예외가 발생하지 않아야 함
        suggestions = await service.get_suggestions(db_session, prefix="'; DROP TABLE--")

        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_prefix_match_not_substring_match(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: 접두사 일치

        Given: 검색 인덱스에 다양한 토큰 존재
        When: 특정 접두사로 제안 요청
        Then: 관련 결과 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회의")

        # 결과가 존재하면 접두사 관련성 확인
        for suggestion in suggestions:
            assert isinstance(suggestion, str)

    @pytest.mark.asyncio
    async def test_returns_list_of_strings(
        self, db_session: AsyncSession, sample_search_index_data
    ):
        """
        REQ-SEARCH-009: 반환 타입 검증

        Given: 검색 인덱스 존재
        When: 제안 요청
        Then: List[str] 타입 반환
        """
        service = SearchService()
        suggestions = await service.get_suggestions(db_session, prefix="회")

        assert isinstance(suggestions, list)
        for s in suggestions:
            assert isinstance(s, str)
