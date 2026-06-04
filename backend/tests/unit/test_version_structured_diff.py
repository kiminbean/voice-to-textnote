"""
SPEC-VERSION-002 단위 테스트.

VersionService.compute_structured_diff()의 회의록 JSON 구조 기반
added / removed / modified 분류 정확성을 검증한다.
"""

from __future__ import annotations

import pytest

from backend.services.version_service import VersionService


@pytest.fixture
def service() -> VersionService:
    return VersionService()


class TestComputeStructuredDiff:
    """구조화 diff 핵심 시나리오."""

    def test_identical_content_reports_no_change(
        self, service: VersionService
    ) -> None:
        content = {
            "summary_text": "동일",
            "sections": [{"title": "A", "content": "내용"}],
            "action_items": [{"id": "x", "text": "할 일"}],
        }
        diff = service.compute_structured_diff(content, content)
        assert diff["changed"] is False
        assert diff["total_changes"] == 0
        assert diff["summary_text"]["changed"] is False
        assert diff["sections"] == {"added": [], "removed": [], "modified": []}
        assert diff["action_items"] == {"added": [], "removed": [], "modified": []}

    def test_summary_text_change_detected(self, service: VersionService) -> None:
        old = {"summary_text": "v1"}
        new = {"summary_text": "v2"}
        diff = service.compute_structured_diff(old, new)
        assert diff["summary_text"]["changed"] is True
        assert diff["summary_text"]["before"] == "v1"
        assert diff["summary_text"]["after"] == "v2"
        assert diff["total_changes"] == 1

    def test_section_added_modified_removed(self, service: VersionService) -> None:
        old = {
            "sections": [
                {"title": "주요 안건", "content": "A안 검토"},
                {"title": "결정 사항", "content": "미정"},
            ]
        }
        new = {
            "sections": [
                {"title": "주요 안건", "content": "A안 검토"},        # 동일
                {"title": "결정 사항", "content": "A안 채택"},        # 수정
                {"title": "후속 액션", "content": "내주까지"},        # 추가
            ]
        }
        diff = service.compute_structured_diff(old, new)
        sec = diff["sections"]
        added_titles = [s["title"] for s in sec["added"]]
        removed_titles = [s["title"] for s in sec["removed"]]
        modified_titles = [s["title"] for s in sec["modified"]]
        assert added_titles == ["후속 액션"]
        assert removed_titles == []
        assert modified_titles == ["결정 사항"]
        # 수정 항목은 before/after 모두 포함
        mod = sec["modified"][0]
        assert mod["before_content"] == "미정"
        assert mod["after_content"] == "A안 채택"

    def test_action_items_matched_by_id(self, service: VersionService) -> None:
        old = {
            "action_items": [
                {"id": "AI-1", "text": "준비", "assignee": "Alice"},
                {"id": "AI-2", "text": "리뷰"},
            ]
        }
        new = {
            "action_items": [
                {"id": "AI-1", "text": "준비", "assignee": "Bob"},   # modified
                {"id": "AI-3", "text": "예산 검토"},                  # added
            ]
        }
        diff = service.compute_structured_diff(old, new)
        ai = diff["action_items"]
        assert [a["key"] for a in ai["added"]] == ["id:AI-3"]
        assert [a["key"] for a in ai["removed"]] == ["id:AI-2"]
        assert [a["key"] for a in ai["modified"]] == ["id:AI-1"]
        # modified 항목은 assignee 변경 추적
        assert ai["modified"][0]["before"]["assignee"] == "Alice"
        assert ai["modified"][0]["after"]["assignee"] == "Bob"

    def test_action_items_fallback_to_text_key(
        self, service: VersionService
    ) -> None:
        # id가 없으면 text 기준 매칭
        old = {"action_items": [{"text": "이메일 발송"}]}
        new = {"action_items": [{"text": "이메일 발송"}, {"text": "재확인"}]}
        diff = service.compute_structured_diff(old, new)
        assert [a["key"] for a in diff["action_items"]["added"]] == ["text:재확인"]
        assert diff["action_items"]["removed"] == []
        assert diff["action_items"]["modified"] == []

    def test_total_changes_aggregates_all(self, service: VersionService) -> None:
        old = {
            "summary_text": "v1",
            "sections": [{"title": "X", "content": "a"}],
            "action_items": [{"id": "1", "text": "t"}],
        }
        new = {
            "summary_text": "v2",                                    # +1
            "sections": [
                {"title": "X", "content": "b"},                      # modified +1
                {"title": "Y", "content": "c"},                      # added +1
            ],
            "action_items": [
                {"id": "2", "text": "u"},                            # added +1, removed +1
            ],
        }
        diff = service.compute_structured_diff(old, new)
        assert diff["total_changes"] == 5
        assert diff["changed"] is True

    def test_malformed_sections_skipped_silently(
        self, service: VersionService
    ) -> None:
        # 잘못된 형식의 section은 무시되어 카운트되지 않음
        old = {"sections": ["문자열", {"title": "ok", "content": "1"}]}
        new = {"sections": [{"title": "ok", "content": "2"}]}
        diff = service.compute_structured_diff(old, new)
        assert diff["sections"]["modified"][0]["title"] == "ok"
        assert diff["sections"]["added"] == []
        assert diff["sections"]["removed"] == []

    def test_missing_fields_treated_as_empty(self, service: VersionService) -> None:
        diff = service.compute_structured_diff({}, {})
        assert diff["changed"] is False
        assert diff["summary_text"]["changed"] is False
        assert diff["summary_text"]["before"] is None
        assert diff["summary_text"]["after"] is None
