"""
SPEC-QA-001: 회의 Q&A 서비스 단위 테스트

대상: services/qa_service.py
  - _format_transcript (순수 함수)
  - _extract_sources (순수 함수)
  - ask (Redis + OpenAI mock)
  - get_history (Redis mock)
"""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas.qa import CrossMeetingSource, QAHistoryItem
from backend.services.qa_service import QAService

# ---------------------------------------------------------------------------
# 헬퍼: async generator mock for redis.scan_iter
# ---------------------------------------------------------------------------


async def _async_iter(items: list) -> AsyncIterator:
    """리스트를 비동기 이터레이터로 변환 (scan_iter mock용)."""
    for item in items:
        yield item


# ---------------------------------------------------------------------------
# 테스트 데이터
# ---------------------------------------------------------------------------

_MINUTES_DATA = {
    "segments": [
        {"speaker": "김철수", "text": "분기 매출이 전년 대비 15% 증가했습니다."},
        {"speaker": "이영희", "text": "신규 제품 출시일은 6월 15일로 확정합시다."},
        {"speaker": "김철수", "text": "마케팅 예산을 20% 증액하겠습니다."},
    ],
}

_MINUTES_DATA_EMPTY_SEGMENTS = {"segments": [], "raw_text": "원본 텍스트입니다."}

_MINUTES_DATA_EMPTY = {"segments": [], "raw_text": ""}


# ---------------------------------------------------------------------------
# _format_transcript
# ---------------------------------------------------------------------------


class TestFormatTranscript:
    """트랜스크립트 포맷 변환 (순수 함수)."""

    def test_segments_to_lines(self):
        svc = QAService()
        result = svc._format_transcript(_MINUTES_DATA)
        assert "[0] 김철수: 분기 매출이 전년 대비 15% 증가했습니다." in result
        assert "[1] 이영희: 신규 제품 출시일은 6월 15일로 확정합시다." in result

    def test_empty_segments_fallback_to_raw_text(self):
        svc = QAService()
        result = svc._format_transcript(_MINUTES_DATA_EMPTY_SEGMENTS)
        assert result == "원본 텍스트입니다."

    def test_empty_everything_returns_empty(self):
        svc = QAService()
        result = svc._format_transcript(_MINUTES_DATA_EMPTY)
        assert result == ""

    def test_no_segments_key_returns_raw_text(self):
        svc = QAService()
        result = svc._format_transcript({"raw_text": "raw"})
        assert result == "raw"


# ---------------------------------------------------------------------------
# _extract_sources
# ---------------------------------------------------------------------------


class TestExtractSources:
    """출처 세그먼트 추출 (순수 함수)."""

    def test_extracts_relevant_segments(self):
        svc = QAService()
        sources = svc._extract_sources(
            question="매출 증가율",
            answer="분기 매출이 전년 대비 15% 증가했습니다.",
            minutes_data=_MINUTES_DATA,
        )
        # 최소 1개 이상 출처 추출
        assert len(sources) >= 1
        assert any("매출" in s.text for s in sources)

    def test_no_segments_returns_empty(self):
        svc = QAService()
        sources = svc._extract_sources(
            question="질문",
            answer="답변",
            minutes_data={"segments": []},
        )
        assert sources == []

    def test_max_five_sources(self):
        svc = QAService()
        # 모든 단어가 겹치도록 긴 answer로 강제
        many_segments = {
            "segments": [
                {"speaker": f"SPEAKER_{i}", "text": f"매출 증가율 분기 전년 대비 테스트 항목 {i}"}
                for i in range(10)
            ]
        }
        sources = svc._extract_sources(
            question="매출",
            answer="매출 증가율 분기 전년 대비 테스트",
            minutes_data=many_segments,
        )
        assert len(sources) <= 5

    def test_source_fields(self):
        svc = QAService()
        sources = svc._extract_sources(
            question="매출",
            answer="분기 매출이 전년 대비 15% 증가했습니다.",
            minutes_data=_MINUTES_DATA,
        )
        if sources:
            s = sources[0]
            assert s.segment_index is not None
            assert s.speaker is not None
            assert s.text is not None


# ---------------------------------------------------------------------------
# ask (Redis + OpenAI mock)
# ---------------------------------------------------------------------------


class TestAsk:
    """Q&A 질문-답변 (Redis + OpenAI mock)."""

    @pytest.mark.asyncio
    async def test_successful_ask(self):
        """정상 질문 시 답변 반환."""
        svc = QAService()

        # Redis mock: 키에 따라 다른 값 반환
        async def _redis_get(key):
            if "task:min:result:" in key:
                return json.dumps(_MINUTES_DATA)
            # 이력 키 → None (이력 없음)
            return None

        redis_mock = AsyncMock()
        redis_mock.get.side_effect = _redis_get
        redis_mock.set = AsyncMock()

        # OpenAI mock
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "분기 매출이 전년 대비 15% 증가했습니다."

        with patch.object(svc, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await svc.ask(
                task_id="test-task",
                question="매출 증가율이 어떻게 되나요?",
                redis_client=redis_mock,
            )

        assert "매출" in result.answer
        assert result.thread_id is not None

    @pytest.mark.asyncio
    async def test_ask_raises_when_no_minutes(self):
        """Redis에 회의록이 없으면 ValueError."""
        svc = QAService()
        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        with pytest.raises(ValueError, match="회의록을 찾을 수 없습니다"):
            await svc.ask(
                task_id="missing-task",
                question="질문",
                redis_client=redis_mock,
            )

    @pytest.mark.asyncio
    async def test_ask_raises_when_empty_transcript(self):
        """회의록 내용이 비어 있으면 ValueError."""
        svc = QAService()
        redis_mock = AsyncMock()
        redis_mock.get.return_value = json.dumps(_MINUTES_DATA_EMPTY)

        with pytest.raises(ValueError, match="회의록 내용이 비어 있습니다"):
            await svc.ask(
                task_id="empty-task",
                question="질문",
                redis_client=redis_mock,
            )

    @pytest.mark.asyncio
    async def test_ask_continues_thread(self):
        """기존 thread_id로 대화 이어가기."""
        svc = QAService()

        async def _redis_get(key):
            if "task:min:result:" in key:
                return json.dumps(_MINUTES_DATA)
            return None

        redis_mock = AsyncMock()
        redis_mock.get.side_effect = _redis_get
        redis_mock.set = AsyncMock()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "답변입니다."

        with patch.object(svc, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await svc.ask(
                task_id="test-task",
                question="질문",
                redis_client=redis_mock,
                thread_id="existing-thread-123",
            )

        assert result.thread_id == "existing-thread-123"


# ---------------------------------------------------------------------------
# ask_across_meetings
# ---------------------------------------------------------------------------


class TestAskAcrossMeetings:
    """여러 회의에 걸친 Q&A 근거 검색."""

    @pytest.mark.asyncio
    async def test_returns_grounded_context_answer(self):
        """검색 근거가 있으면 출처 목록과 안전한 요약 답변을 반환한다."""
        from datetime import datetime

        from backend.schemas.search import SearchResponse, SearchResultItem, SortOption

        svc = QAService()
        search_service = AsyncMock()
        search_service.find_answer_contexts.return_value = SearchResponse(
            items=[
                SearchResultItem(
                    task_id="sum-search-001",
                    task_type="summary",
                    snippet="회의 결과 <b>FastAPI</b> 사용을 결정했습니다.",
                    created_at=datetime(2024, 1, 3, 9, 0, 0),
                    completed_at=datetime(2024, 1, 3, 9, 5, 0),
                )
            ],
            total=1,
            page=1,
            page_size=5,
            query="API 결정",
            sort=SortOption.RELEVANCE,
        )

        result = await svc.ask_across_meetings(
            session=AsyncMock(),
            question="API 결정은?",
            search_service=search_service,
        )

        assert result.query == "API 결정"
        assert result.total == 1
        assert result.sources[0].task_id == "sum-search-001"
        assert "관련된 회의 근거 1건" in result.answer

    @pytest.mark.asyncio
    async def test_raises_when_no_contexts(self):
        """검색 근거가 없으면 명확한 ValueError를 낸다."""
        from backend.schemas.search import SearchResponse, SortOption

        svc = QAService()
        search_service = AsyncMock()
        search_service.find_answer_contexts.return_value = SearchResponse(
            items=[],
            total=0,
            page=1,
            page_size=5,
            query="없는 질문",
            sort=SortOption.RELEVANCE,
        )

        with pytest.raises(ValueError, match="회의 근거를 찾을 수 없습니다"):
            await svc.ask_across_meetings(
                session=AsyncMock(),
                question="없는 질문",
                search_service=search_service,
            )

    def test_build_cross_meeting_answer_lists_sources(self):
        """근거 요약 답변은 검색 스니펫을 그대로 포함한다."""
        svc = QAService()
        answer = svc._build_cross_meeting_answer(
            "API 결정은?",
            [
                CrossMeetingSource(
                    task_id="task-1",
                    task_type="summary",
                    snippet="FastAPI 결정",
                    created_at="2024-01-01T09:00:00",
                )
            ],
        )

        assert "API 결정은?" in answer
        assert "task-1" in answer
        assert "FastAPI 결정" in answer


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    """Q&A 이력 조회 (Redis mock)."""

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """이력이 없으면 빈 응답."""
        svc = QAService()
        redis_mock = AsyncMock()
        # scan_iter는 sync 함수로 오버라이드 (async generator 반환)
        redis_mock.scan_iter = MagicMock(return_value=_async_iter([]))

        result = await svc.get_history(
            task_id="no-history-task",
            redis_client=redis_mock,
        )
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_returns_history_sorted_by_time(self):
        """여러 thread의 이력을 시간순 정렬."""
        svc = QAService()

        history_data = [
            {
                "question": "첫 번째 질문",
                "answer": "첫 번째 답변",
                "sources": [],
                "created_at": "2026-01-01T10:00:00",
            },
            {
                "question": "두 번째 질문",
                "answer": "두 번째 답변",
                "sources": [],
                "created_at": "2026-01-01T11:00:00",
            },
        ]

        redis_mock = AsyncMock()
        redis_mock.scan_iter = MagicMock(return_value=_async_iter(["qa:history:task1:thread1"]))
        redis_mock.get.return_value = json.dumps(history_data)

        result = await svc.get_history(
            task_id="task1",
            redis_client=redis_mock,
        )
        assert result.total == 2
        assert result.items[0].question == "첫 번째 질문"
        assert result.items[1].question == "두 번째 질문"


# ---------------------------------------------------------------------------
# _save_history / _load_history (간접 테스트)
# ---------------------------------------------------------------------------


class TestHistoryIO:
    """Redis 이력 저장/로드."""

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self):
        """저장 후 로드하면 동일 데이터 반환."""
        svc = QAService()
        redis_mock = AsyncMock()

        item = QAHistoryItem(
            question="질문",
            answer="답변",
            sources=[],
            created_at="2026-01-01T10:00:00",
        )

        # save: get → None(최초), set
        redis_mock.get.return_value = None
        await svc._save_history(redis_mock, "task1", "thread1", item)

        # save가 set을 호출했는지 확인
        redis_mock.set.assert_called_once()
        saved_key = redis_mock.set.call_args[0][0]
        saved_value = redis_mock.set.call_args[0][1]
        assert "qa:history:task1:thread1" == saved_key

        # load: get → 저장된 값
        redis_mock.get.return_value = saved_value
        loaded = await svc._load_history(redis_mock, "task1", "thread1")
        assert len(loaded) == 1
        assert loaded[0].question == "질문"
        assert loaded[0].answer == "답변"


class TestGetClient:
    """_get_client() 메서드 테스트"""

    @patch("backend.services.qa_service.settings")
    def test_returns_openai_client(self, mock_settings):
        """_get_client가 OpenAI 클라이언트를 반환한다"""
        from openai import OpenAI

        mock_settings.openai_api_key = "test-key"
        svc = QAService()
        client = svc._get_client()
        assert isinstance(client, OpenAI)


class TestBuildMessagesWithHistory:
    """_build_messages() 히스토리 포함 테스트"""

    @pytest.mark.asyncio
    async def test_includes_history_messages(self):
        """이전 대화 이력이 메시지에 포함된다"""
        from unittest.mock import AsyncMock

        svc = QAService()

        # 히스토리 모킹 — _load_history가 2개 아이템 반환
        history_items = [
            MagicMock(question="Q1", answer="A1"),
            MagicMock(question="Q2", answer="A2"),
        ]
        svc._load_history = AsyncMock(return_value=history_items)

        redis_mock = AsyncMock()
        messages = await svc._build_messages(
            redis_mock, "task1", "thread1", "현재 질문", "트랜스크립트"
        )

        # 시스템 메시지 + 히스토리(2쌍=4개) + 현재 질문 = 최소 6개
        assert len(messages) >= 6

        # 히스토리의 user/assistant 메시지가 포함되었는지 확인
        user_contents = [m["content"] for m in messages if m["role"] == "user"]
        assistant_contents = [m["content"] for m in messages if m["role"] == "assistant"]
        assert "Q1" in user_contents
        assert "A1" in assistant_contents
