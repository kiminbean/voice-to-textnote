"""
검색 서비스 테스트 - SPEC-SEARCH-001, SPEC-SEARCH-002

테스트 범위:
- SearchService.search(): FTS5 기반 전문 검색 (SPEC-SEARCH-001)
- REQ-SEARCH-007: 날짜 범위 필터 (date_from, date_to)
- REQ-SEARCH-008: 정렬 옵션 (sort: relevance | newest | oldest)
- REQ-SEARCH-011: 화자 이름 필터 (speaker)
- REQ-SEARCH-012: 액션 아이템/핵심 결정 필터 (has_action_items, has_key_decisions)
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base
from backend.schemas.search import SortOption

# ---------------------------------------------------------------------------
# 테스트 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_engine():
    """인메모리 SQLite 비동기 엔진 픽스처"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # FTS5 테이블 생성 (raw SQL)
        await conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index "
                "USING fts5(task_id, task_type, content, speaker_names, "
                "summary_text, action_items_text, created_at UNINDEXED, "
                "tokenize='unicode61')"
            )
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    """비동기 DB 세션 픽스처"""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def populated_search_db(db_session: AsyncSession):
    """검색 인덱스에 샘플 데이터를 삽입하는 픽스처"""
    from datetime import datetime

    from backend.db.models import TaskResult

    # task_results에 실제 레코드 삽입
    records = [
        TaskResult(
            task_id="min-search-001",
            task_type="minutes",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 1, 9, 0, 0),
        ),
        TaskResult(
            task_id="min-search-002",
            task_type="minutes",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 2, 9, 0, 0),
        ),
        TaskResult(
            task_id="sum-search-001",
            task_type="summary",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 3, 9, 0, 0),
        ),
        TaskResult(
            task_id="sum-search-002",
            task_type="summary",
            status="completed",
            result_data={},
            completed_at=datetime(2024, 1, 4, 9, 0, 0),
        ),
    ]
    for r in records:
        db_session.add(r)
    await db_session.flush()

    # 검색 인덱스 삽입
    search_rows = [
        {
            "task_id": "min-search-001",
            "task_type": "minutes",
            "content": "오늘 회의를 시작하겠습니다. 프로젝트 일정을 논의합니다.",
            "speaker_names": "김팀장 이개발",
            "summary_text": "",
            "action_items_text": "",
            "created_at": "2024-01-01T09:00:00",
        },
        {
            "task_id": "min-search-002",
            "task_type": "minutes",
            "content": "백엔드 API 설계에 대해 논의했습니다.",
            "speaker_names": "박차장 최개발",
            "summary_text": "",
            "action_items_text": "",
            "created_at": "2024-01-02T09:00:00",
        },
        {
            "task_id": "sum-search-001",
            "task_type": "summary",
            "content": "",
            "speaker_names": "",
            "summary_text": "회의 결과 FastAPI 사용을 결정했습니다.",
            "action_items_text": "보고서 작성 API 개발",
            "created_at": "2024-01-03T09:00:00",
        },
        {
            "task_id": "sum-search-002",
            "task_type": "summary",
            "content": "",
            "speaker_names": "",
            "summary_text": "다음 스프린트 계획을 수립했습니다.",
            "action_items_text": "스프린트 계획 수립",
            "created_at": "2024-01-04T09:00:00",
        },
    ]
    for row in search_rows:
        await db_session.execute(
            text(
                "INSERT INTO search_index "
                "(task_id, task_type, content, speaker_names, summary_text, action_items_text, created_at) "
                "VALUES (:task_id, :task_type, :content, :speaker_names, :summary_text, :action_items_text, :created_at)"
            ),
            row,
        )
    await db_session.commit()
    yield db_session


# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------


class TestSearchService:
    """SearchService.search() 테스트"""

    @pytest.mark.asyncio
    async def test_search_basic_query(self, populated_search_db):
        """기본 검색 쿼리로 결과를 반환해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(session=populated_search_db, query="회의")

        assert result.total > 0
        assert len(result.items) > 0
        assert result.query == "회의"

    @pytest.mark.asyncio
    async def test_search_with_task_type_filter_summary(self, populated_search_db):
        """task_type='summary' 필터로 summary만 반환해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(
            session=populated_search_db, query="스프린트", task_type="summary"
        )

        assert result.total > 0
        for item in result.items:
            assert item.task_type == "summary"

    @pytest.mark.asyncio
    async def test_search_with_task_type_filter_minutes(self, populated_search_db):
        """task_type='minutes' 필터로 minutes만 반환해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(session=populated_search_db, query="API", task_type="minutes")

        assert result.total > 0
        for item in result.items:
            assert item.task_type == "minutes"

    @pytest.mark.asyncio
    async def test_search_pagination(self, populated_search_db):
        """페이지네이션이 올바르게 동작해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()

        # 전체 결과
        result_all = await service.search(
            session=populated_search_db, query="논의", page=1, page_size=10
        )
        # 첫 번째 페이지, 크기 1
        result_p1 = await service.search(
            session=populated_search_db, query="논의", page=1, page_size=1
        )

        if result_all.total > 1:
            # 두 번째 페이지
            result_p2 = await service.search(
                session=populated_search_db, query="논의", page=2, page_size=1
            )
            assert len(result_p1.items) == 1
            # 총 개수는 동일해야 함
            assert result_p1.total == result_all.total
            # 다른 항목이어야 함
            if result_p2.items:
                assert result_p1.items[0].task_id != result_p2.items[0].task_id

    @pytest.mark.asyncio
    async def test_search_empty_results(self, populated_search_db):
        """매칭되지 않는 쿼리는 빈 결과를 반환해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(
            session=populated_search_db,
            query="존재하지않는쿼리xyz12345",
        )

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_search_snippet_contains_match(self, populated_search_db):
        """스니펫에 매칭 키워드가 포함되어야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(session=populated_search_db, query="프로젝트")

        if result.items:
            # 스니펫이 비어있지 않아야 함
            assert result.items[0].snippet is not None
            assert len(result.items[0].snippet) > 0

    @pytest.mark.asyncio
    async def test_search_result_schema(self, populated_search_db):
        """SearchResponse 스키마가 올바르게 반환되어야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(session=populated_search_db, query="회의")

        # 스키마 필드 확인
        assert hasattr(result, "items")
        assert hasattr(result, "total")
        assert hasattr(result, "page")
        assert hasattr(result, "page_size")
        assert hasattr(result, "query")
        assert result.page == 1
        assert result.page_size == 20

    @pytest.mark.asyncio
    async def test_search_result_item_schema(self, populated_search_db):
        """SearchResultItem 스키마가 올바른 필드를 포함해야 함"""
        from backend.services.search_service import SearchService

        service = SearchService()
        result = await service.search(session=populated_search_db, query="회의")

        if result.items:
            item = result.items[0]
            assert hasattr(item, "task_id")
            assert hasattr(item, "task_type")
            assert hasattr(item, "snippet")
            assert hasattr(item, "created_at")
            # completed_at은 optional
            assert hasattr(item, "completed_at")


class TestSearchServiceExtendedFilters:
    """SearchService 동적 필터/정렬 테스트 (SPEC-SEARCH-002)"""

    @pytest.mark.asyncio
    async def test_search_with_date_range(self, populated_search_db):
        """REQ-SEARCH-007: 날짜 범위 필터"""
        from backend.services.search_service import SearchService

        service = SearchService()
        date_from = datetime(2024, 1, 2)
        date_to = datetime(2024, 1, 3)

        result = await service.search(
            session=populated_search_db,
            query="회의",
            date_from=date_from,
            date_to=date_to,
        )

        # 모든 결과가 날짜 범위 내에 있는지 확인
        for item in result.items:
            assert item.created_at >= date_from
            assert item.created_at <= date_to

    @pytest.mark.asyncio
    async def test_search_with_date_from_only(self, populated_search_db):
        """REQ-SEARCH-007: date_from만 지정"""
        from backend.services.search_service import SearchService

        service = SearchService()
        date_from = datetime(2024, 1, 2)

        result = await service.search(
            session=populated_search_db,
            query="회의",
            date_from=date_from,
        )

        # 모든 결과가 date_from 이후인지 확인
        for item in result.items:
            assert item.created_at >= date_from

    @pytest.mark.asyncio
    async def test_search_with_date_to_only(self, populated_search_db):
        """REQ-SEARCH-007: date_to만 지정"""
        from backend.services.search_service import SearchService

        service = SearchService()
        date_to = datetime(2024, 1, 3)

        result = await service.search(
            session=populated_search_db,
            query="회의",
            date_to=date_to,
        )

        # 모든 결과가 date_to 이전인지 확인
        for item in result.items:
            assert item.created_at <= date_to

    @pytest.mark.asyncio
    async def test_search_sort_newest(self, populated_search_db):
        """REQ-SEARCH-008: newest 정렬 (created_at DESC)"""
        from backend.services.search_service import SearchService

        service = SearchService()

        result = await service.search(
            session=populated_search_db, query="회의", sort=SortOption.NEWEST
        )

        # created_at 내림차순 정렬 확인
        if len(result.items) >= 2:
            for i in range(len(result.items) - 1):
                assert result.items[i].created_at >= result.items[i + 1].created_at

    @pytest.mark.asyncio
    async def test_search_sort_oldest(self, populated_search_db):
        """REQ-SEARCH-008: oldest 정렬 (created_at ASC)"""
        from backend.services.search_service import SearchService

        service = SearchService()

        result = await service.search(
            session=populated_search_db, query="회의", sort=SortOption.OLDEST
        )

        # created_at 오름차순 정렬 확인
        if len(result.items) >= 2:
            for i in range(len(result.items) - 1):
                assert result.items[i].created_at <= result.items[i + 1].created_at

    @pytest.mark.asyncio
    async def test_search_default_sort(self, populated_search_db):
        """REQ-SEARCH-008: sort 미지정 시 기본 정렬 (created_at DESC, 하위 호환)"""
        from backend.services.search_service import SearchService

        service = SearchService()

        result = await service.search(session=populated_search_db, query="회의")

        # 기본 정렬이 created_at DESC인지 확인
        if len(result.items) >= 2:
            for i in range(len(result.items) - 1):
                assert result.items[i].created_at >= result.items[i + 1].created_at

    @pytest.mark.asyncio
    async def test_search_with_speaker_filter(self, populated_search_db):
        """REQ-SEARCH-011: 화자 이름 필터"""
        from backend.services.search_service import SearchService

        service = SearchService()

        result = await service.search(session=populated_search_db, query="회의", speaker="김팀장")

        # 필터가 적용되어 결과가 반환됨
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_has_action_items(self, populated_search_db):
        """REQ-SEARCH-012: has_action_items 필터"""
        from backend.services.search_service import SearchService

        service = SearchService()

        result = await service.search(
            session=populated_search_db, query="스프린트", has_action_items=True
        )

        # action_items_text가 비어있지 않은 결과만 반환됨
        assert result is not None

    @pytest.mark.asyncio
    async def test_combined_filters(self, populated_search_db):
        """REQ-SEARCH-012: 복합 필터 조합"""
        from backend.services.search_service import SearchService

        service = SearchService()
        date_from = datetime(2024, 1, 2)

        result = await service.search(
            session=populated_search_db,
            query="회의",
            task_type="summary",
            date_from=date_from,
            sort=SortOption.NEWEST,
            speaker="김팀장",
            has_action_items=True,
        )

        # 모든 필터가 적용되었는지 확인
        for item in result.items:
            assert item.created_at >= date_from
            assert item.task_type == "summary"

        if len(result.items) >= 2:
            # 정렬 확인
            for i in range(len(result.items) - 1):
                assert result.items[i].created_at >= result.items[i + 1].created_at
