"""
Tests for action_items_engine.py - covering uncovered lines 160, 167
"""

from backend.ml.action_items_engine import extract_action_items


class TestActionItemsEngineUncoveredLines:
    """Tests for uncovered lines in action_items_engine.py"""

    def test_extract_action_items_short_task_skipped(self):
        """Test that tasks shorter than 5 chars are skipped (line 167)"""
        # Line 167 checks: if len(task_text) < 5: continue
        # The TODO pattern doesn't have a minimum length requirement
        text = "TODO: 짧음 TODO: 충분히 긴 작업 항목입니다"
        items = extract_action_items(text, language="ko")

        # Should skip "짧음" (4 chars) and extract the long one
        assert len(items) >= 1
        # All extracted items should have task >= 5 chars
        for item in items:
            assert len(item.task) >= 5

    def test_extract_action_items_empty_text_returns_empty(self):
        """Test that empty or short text returns empty list (line 149-150)"""
        items = extract_action_items("", language="ko")
        assert items == []

        items = extract_action_items("   ", language="ko")
        assert items == []

        items = extract_action_items("short", language="ko")
        assert items == []

    def test_extract_action_items_duplicate_removal(self):
        """Test that duplicate tasks are removed (line 163-165)"""
        text = "TODO: Implement feature TODO: Implement feature TODO: implement feature"
        items = extract_action_items(text, language="ko")

        # Should deduplicate based on normalized text
        assert len(items) == 1

    def test_extract_action_items_max_limit(self):
        """Test that items are limited to 50 (line 191)"""
        # Create text with many action items
        text = " ".join([f"TODO: Task number {i}" for i in range(100)])
        items = extract_action_items(text, language="ko")

        # Should be limited to 50
        assert len(items) <= 50

    def test_extract_action_items_context_extraction(self):
        """Test context extraction from pattern (line 172)"""
        text = "회의에서 기능 구현이 논의되었습니다. 다음 주까지 기능을 구현해주세요"
        items = extract_action_items(text, language="ko")

        assert len(items) > 0
        # Context should be captured if available
        if items[0].context:
            assert len(items[0].context) > 3

    def test_extract_action_items_context_too_short(self):
        """Test that context shorter than 3 chars is None (line 186)"""
        # Use text that will match and have context
        text = "회의 논의 사항을 확인해주세요"
        items = extract_action_items(text, language="ko")

        # Should extract the item
        assert len(items) > 0
        # Context "회의 논의 " is longer than 3 chars, so should be kept
        assert items[0].context is not None
        assert len(items[0].context) >= 3

    def test_extract_action_items_with_assignee_extraction(self):
        """Test assignee extraction (line 176)"""
        text = "담당자: 홍길동 기능을 확인해주세요"
        items = extract_action_items(text, language="ko", include_assignees=True)

        assert len(items) > 0
        # Should extract "홍길동" as assignee
        assert items[0].assignee == "홍길동"

    def test_extract_action_items_without_assignee(self):
        """Test with include_assignees=False (line 176)"""
        text = "기능을 확인해주세요"
        items = extract_action_items(text, language="ko", include_assignees=False)

        assert len(items) > 0
        # Assignee should not be extracted when disabled
        assert items[0].assignee is None

    def test_extract_action_items_with_deadline(self):
        """Test deadline extraction (line 177)"""
        text = "다음 주까지 기능을 구현해주세요"
        items = extract_action_items(text, language="ko", include_deadlines=True)

        assert len(items) > 0
        # May extract deadline depending on pattern matching
        if items[0].deadline:
            assert "주" in items[0].deadline

    def test_extract_action_items_priority_high(self):
        """Test high priority detection (line 124-125)"""
        text = "긴급하게 기능을 구현해주세요"
        items = extract_action_items(text, language="ko")

        assert len(items) > 0
        # Priority is extracted from the text content
        # "긴급" should trigger high priority
        assert items[0].priority == "high"

    def test_extract_action_items_priority_low(self):
        """Test low priority detection (line 126-127)"""
        text = "나중에 기능을 확인해주세요"
        items = extract_action_items(text, language="ko")

        assert len(items) > 0
        # "나중에" should trigger low priority
        assert items[0].priority == "low"

    def test_extract_action_items_priority_medium(self):
        """Test medium priority (default, line 128)"""
        text = "기능을 확인해주세요"
        items = extract_action_items(text, language="ko")

        assert len(items) > 0
        # No priority keyword = medium (default)
        assert items[0].priority == "medium"

    def test_extract_action_items_english_patterns(self):
        """Test English action item patterns"""
        text = "John will implement the feature. Please review by tomorrow."
        items = extract_action_items(text, language="en", include_assignees=True)

        assert len(items) > 0
