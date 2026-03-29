"""
요약 스키마 단위 테스트 (RED phase)
REQ-SUM-005: ActionItem, SummaryCreateRequest, SummaryResult, SummaryResponse, SummaryStatusResponse
"""

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# ActionItem 스키마 테스트
# ---------------------------------------------------------------------------


class TestActionItemSchema:
    """ActionItem 스키마 검증"""

    def test_action_item_with_all_fields(self):
        """모든 필드 포함 ActionItem 생성"""
        from backend.schemas.summary import ActionItem

        item = ActionItem(
            assignee="김팀장",
            task="보고서 작성",
            deadline="2025-01-15",
            priority="high",
        )
        assert item.assignee == "김팀장"
        assert item.task == "보고서 작성"
        assert item.deadline == "2025-01-15"
        assert item.priority == "high"

    def test_action_item_with_required_only(self):
        """필수 필드(task)만 포함 - 나머지는 기본값/None"""
        from backend.schemas.summary import ActionItem

        item = ActionItem(task="보고서 작성")
        assert item.task == "보고서 작성"
        assert item.assignee is None
        assert item.deadline is None
        assert item.priority == "medium"  # 기본값

    def test_action_item_priority_default_is_medium(self):
        """priority 기본값 = 'medium' (REQ-SUM-005)"""
        from backend.schemas.summary import ActionItem

        item = ActionItem(task="테스트 작업")
        assert item.priority == "medium"

    def test_action_item_assignee_nullable(self):
        """assignee는 None 허용 (str|None)"""
        from backend.schemas.summary import ActionItem

        item = ActionItem(task="작업", assignee=None)
        assert item.assignee is None

    def test_action_item_deadline_nullable(self):
        """deadline은 None 허용 (str|None)"""
        from backend.schemas.summary import ActionItem

        item = ActionItem(task="작업", deadline=None)
        assert item.deadline is None

    def test_action_item_missing_task_raises_error(self):
        """task 필드 누락 → ValidationError"""
        from backend.schemas.summary import ActionItem

        with pytest.raises(ValidationError):
            ActionItem()


# ---------------------------------------------------------------------------
# SummaryCreateRequest 스키마 테스트
# ---------------------------------------------------------------------------


class TestSummaryCreateRequestSchema:
    """SummaryCreateRequest 스키마 검증"""

    def test_create_request_with_required_only(self):
        """필수 필드(minutes_task_id)만으로 생성"""
        from backend.schemas.summary import SummaryCreateRequest

        req = SummaryCreateRequest(minutes_task_id="min-task-123")
        assert req.minutes_task_id == "min-task-123"
        assert req.max_tokens == 4096  # 기본값 (2000→4096 변경됨)

    def test_create_request_max_tokens_default(self):
        """max_tokens 기본값 = 4096 (REQ-SUM-005)"""
        from backend.schemas.summary import SummaryCreateRequest

        req = SummaryCreateRequest(minutes_task_id="test-id")
        assert req.max_tokens == 4096

    def test_create_request_custom_max_tokens(self):
        """max_tokens 커스텀 값 설정"""
        from backend.schemas.summary import SummaryCreateRequest

        req = SummaryCreateRequest(minutes_task_id="test-id", max_tokens=1000)
        assert req.max_tokens == 1000

    def test_create_request_missing_minutes_task_id_raises_error(self):
        """minutes_task_id 누락 → ValidationError"""
        from backend.schemas.summary import SummaryCreateRequest

        with pytest.raises(ValidationError):
            SummaryCreateRequest()


# ---------------------------------------------------------------------------
# SummaryResult 스키마 테스트
# ---------------------------------------------------------------------------


class TestSummaryResultSchema:
    """SummaryResult 스키마 검증"""

    def test_summary_result_with_all_fields(self):
        """모든 필드 포함 SummaryResult 생성"""
        from backend.schemas.summary import ActionItem, SummaryResult

        result = SummaryResult(
            summary_text="회의 요약 텍스트",
            action_items=[ActionItem(task="작업1")],
            key_decisions=["결정1", "결정2"],
            next_steps=["다음 단계1"],
        )
        assert result.summary_text == "회의 요약 텍스트"
        assert len(result.action_items) == 1
        assert len(result.key_decisions) == 2
        assert len(result.next_steps) == 1

    def test_summary_result_empty_lists(self):
        """action_items, key_decisions, next_steps 빈 리스트 허용"""
        from backend.schemas.summary import SummaryResult

        result = SummaryResult(
            summary_text="요약",
            action_items=[],
            key_decisions=[],
            next_steps=[],
        )
        assert result.action_items == []
        assert result.key_decisions == []
        assert result.next_steps == []

    def test_summary_result_missing_summary_text_raises_error(self):
        """summary_text 누락 → ValidationError"""
        from backend.schemas.summary import SummaryResult

        with pytest.raises(ValidationError):
            SummaryResult(action_items=[], key_decisions=[], next_steps=[])


# ---------------------------------------------------------------------------
# SummaryResponse 스키마 테스트
# ---------------------------------------------------------------------------


class TestSummaryResponseSchema:
    """SummaryResponse 스키마 검증"""

    def test_summary_response_basic(self):
        """기본 SummaryResponse 생성"""
        from backend.schemas.summary import SummaryResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryResponse(
            task_id="task-123",
            status=TaskStatus.completed,
            minutes_task_id="min-task-456",
            summary_text="요약 텍스트",
            action_items=[],
            key_decisions=[],
            next_steps=[],
        )
        assert resp.task_id == "task-123"
        assert resp.status == TaskStatus.completed
        assert resp.minutes_task_id == "min-task-456"
        assert resp.summary_text == "요약 텍스트"

    def test_summary_response_optional_fields_none(self):
        """tokens_used, generation_time_seconds는 None 허용"""
        from backend.schemas.summary import SummaryResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryResponse(
            task_id="task-123",
            status=TaskStatus.pending,
            minutes_task_id="min-task-456",
            summary_text="",
            action_items=[],
            key_decisions=[],
            next_steps=[],
        )
        assert resp.tokens_used is None
        assert resp.generation_time_seconds is None

    def test_summary_response_with_tokens_used(self):
        """tokens_used dict 설정 가능"""
        from backend.schemas.summary import SummaryResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryResponse(
            task_id="task-123",
            status=TaskStatus.completed,
            minutes_task_id="min-task-456",
            summary_text="요약",
            action_items=[],
            key_decisions=[],
            next_steps=[],
            tokens_used={"input_tokens": 100, "output_tokens": 50},
        )
        assert resp.tokens_used == {"input_tokens": 100, "output_tokens": 50}

    def test_summary_response_with_generation_time(self):
        """generation_time_seconds float 설정 가능"""
        from backend.schemas.summary import SummaryResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryResponse(
            task_id="task-123",
            status=TaskStatus.completed,
            minutes_task_id="min-task-456",
            summary_text="요약",
            action_items=[],
            key_decisions=[],
            next_steps=[],
            generation_time_seconds=3.14,
        )
        assert resp.generation_time_seconds == 3.14


# ---------------------------------------------------------------------------
# SummaryStatusResponse 스키마 테스트
# ---------------------------------------------------------------------------


class TestSummaryStatusResponseSchema:
    """SummaryStatusResponse 스키마 검증"""

    def test_status_response_basic(self):
        """기본 SummaryStatusResponse 생성"""
        from backend.schemas.summary import SummaryStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryStatusResponse(
            task_id="task-123",
            status=TaskStatus.processing,
            progress=0.5,
        )
        assert resp.task_id == "task-123"
        assert resp.status == TaskStatus.processing
        assert resp.progress == 0.5

    def test_status_response_message_optional(self):
        """message 필드는 None 허용"""
        from backend.schemas.summary import SummaryStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryStatusResponse(
            task_id="task-123",
            status=TaskStatus.pending,
            progress=0.0,
        )
        assert resp.message is None

    def test_status_response_uses_task_status_enum(self):
        """status 필드는 TaskStatus enum 사용"""
        from backend.schemas.summary import SummaryStatusResponse
        from backend.schemas.transcription import TaskStatus

        resp = SummaryStatusResponse(
            task_id="task-123",
            status=TaskStatus.failed,
            progress=0.0,
        )
        assert resp.status == TaskStatus.failed
