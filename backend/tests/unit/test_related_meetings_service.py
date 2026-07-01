"""
관련 회의 추천 서비스 테스트 - SPEC-RELATED-001

테스트 범위:
- RelatedMeetingsService.find_related(): FTS5 + 키워드 기반 관련 회의 탐색
- 기준 회의 제외, 공유 키워드 계산, 관련도 정렬, 접근제어(owner) 필터
- 인덱스 부재/짧은 텍스트 등 방어적 경로
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, TaskResult
from backend.services.related_meetings_service import RelatedMeetingsService

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_engine():
    """인메모리 SQLite 비동기 엔진 (FTS5 search_index 포함)"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def _insert_meeting(
    session: AsyncSession,
    task_id: str,
    task_type: str,
    *,
    content: str = "",
    summary_text: str = "",
    action_items_text: str = "",
    speaker_names: str = "",
    created_at: str = "2024-01-01T09:00:00",
) -> None:
    """task_results + search_index에 한 회의를 삽입한다."""
    session.add(
        TaskResult(
            task_id=task_id,
            task_type=task_type,
            status="completed",
            result_data={},
            completed_at=datetime.fromisoformat(created_at),
        )
    )
    await session.flush()
    await session.execute(
        text(
            "INSERT INTO search_index "
            "(task_id, task_type, content, speaker_names, summary_text, "
            "action_items_text, created_at) VALUES "
            "(:task_id, :task_type, :content, :speaker_names, :summary_text, "
            ":action_items_text, :created_at)"
        ),
        {
            "task_id": task_id,
            "task_type": task_type,
            "content": content,
            "speaker_names": speaker_names,
            "summary_text": summary_text,
            "action_items_text": action_items_text,
            "created_at": created_at,
        },
    )


@pytest_asyncio.fixture
async def populated_session(db_session: AsyncSession) -> AsyncSession:
    """겹치는 키워드를 가진 여러 회의를 삽입한다."""
    # 기준 회의: 백엔드/API/데이터베이스/인덱스 관련
    await _insert_meeting(
        db_session,
        "src-001",
        "minutes",
        content="백엔드 API 설계 회의입니다. 데이터베이스 스키마 인덱스 최적화 방안을 논의했습니다.",
        speaker_names="김팀장 이개발",
        created_at="2024-01-01T09:00:00",
    )
    # 높은 겹침: 동일 키워드 다수 반복
    await _insert_meeting(
        db_session,
        "rel-high",
        "minutes",
        content="백엔드 API 설계 리뷰. 데이터베이스 인덱스 튜닝과 스키마 검토를 진행했습니다.",
        created_at="2024-01-02T09:00:00",
    )
    # 부분 겹침: 데이터베이스/스키마만 공유
    await _insert_meeting(
        db_session,
        "rel-partial",
        "minutes",
        content="데이터베이스 스키마 마이그레이션 계획을 세웠습니다.",
        created_at="2024-01-03T09:00:00",
    )
    # 무관: 겹치는 키워드 없음 -> FTS MATCH 단계에서 제외되어야 함
    await _insert_meeting(
        db_session,
        "rel-none",
        "summary",
        summary_text="마케팅 캠페인 예산 광고 채널 배분을 결정했습니다.",
        created_at="2024-01-04T09:00:00",
    )
    await db_session.commit()
    return db_session


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


class TestFindRelated:
    @pytest.mark.asyncio
    async def test_returns_related_and_excludes_source(self, populated_session):
        svc = RelatedMeetingsService()
        result = await svc.find_related(populated_session, "src-001")

        assert result.source_task_id == "src-001"
        assert result.keywords, "기준 회의에서 키워드가 추출되어야 한다"
        returned_ids = {item.task_id for item in result.items}
        # 기준 회의는 결과에서 제외
        assert "src-001" not in returned_ids
        # 높은 겹침 회의는 포함
        assert "rel-high" in returned_ids
        # 무관한 회의는 제외 (공유 키워드 없음 -> FTS 미매칭)
        assert "rel-none" not in returned_ids
        assert result.total == len(result.items)

    @pytest.mark.asyncio
    async def test_sorted_by_score_descending(self, populated_session):
        svc = RelatedMeetingsService()
        result = await svc.find_related(populated_session, "src-001")

        scores = [item.score for item in result.items]
        assert scores == sorted(scores, reverse=True)
        for item in result.items:
            assert 0.0 <= item.score <= 1.0
            assert item.shared_keywords, "관련 회의는 최소 1개 공유 키워드를 가져야 한다"

    @pytest.mark.asyncio
    async def test_high_overlap_ranks_above_partial(self, populated_session):
        svc = RelatedMeetingsService()
        result = await svc.find_related(populated_session, "src-001")

        order = [item.task_id for item in result.items]
        assert "rel-high" in order and "rel-partial" in order
        # 겹침이 많은 회의가 부분 겹침보다 앞서야 한다
        assert order.index("rel-high") < order.index("rel-partial")

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, populated_session):
        svc = RelatedMeetingsService()
        result = await svc.find_related(populated_session, "src-001", limit=1)
        assert len(result.items) <= 1

    @pytest.mark.asyncio
    async def test_unknown_source_returns_empty(self, populated_session):
        svc = RelatedMeetingsService()
        result = await svc.find_related(populated_session, "does-not-exist")
        assert result.items == []
        assert result.total == 0
        assert result.keywords == []

    @pytest.mark.asyncio
    async def test_owner_filter_excludes_inaccessible(self, populated_session):
        """소유자 컨텍스트가 있으면 접근 가능한 회의만 반환한다."""
        import uuid

        svc = RelatedMeetingsService()
        # 어떤 meeting_ownership도 없는 임의 사용자 -> 접근 가능한 회의 없음
        result = await svc.find_related(
            populated_session,
            "src-001",
            owner_id=uuid.uuid4(),
        )
        assert result.items == []
