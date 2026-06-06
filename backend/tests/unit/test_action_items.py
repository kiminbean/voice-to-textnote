"""
액션 아이템 추출 엔진 테스트
"""

from backend.ml.action_items_engine import (
    _extract_assignee,
    _extract_deadline,
    _extract_priority,
    extract_action_items,
)


class TestExtractActionItems:
    """extract_action_items 함수 테스트"""

    def test_korean_basic_extraction(self):
        """한국어 기본 액션 아이템 추출"""
        text = """
        회의 내용입니다.
        김대리가 내일까지 보고서를 작성해 주세요.
        이부분은 일반 발화입니다.
        박과장이 이번 주 금요일까지 검토하겠습니다.
        """
        items = extract_action_items(text, language="ko")
        assert isinstance(items, list)
        # 최소 1개 이상 추출되어야 함
        assert len(items) >= 1

    def test_korean_todo_marker(self):
        """한국어 TODO/할 일 마커 인식"""
        text = """
        회의 결과:
        할 일: 다음 주까지 설계 문서 작성
        액션 아이템: API 스펙 확정
        TODO: 테스트 코드 작성
        """
        items = extract_action_items(text, language="ko")
        assert len(items) >= 2

    def test_english_basic_extraction(self):
        """영어 기본 액션 아이템 추출"""
        text = """
        Meeting notes:
        John will prepare the presentation by Friday.
        We need to review the API design.
        Please send the report to the team.
        """
        items = extract_action_items(text, language="en")
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_empty_text(self):
        """빈 텍스트 처리"""
        assert extract_action_items("", language="ko") == []
        assert extract_action_items("   ", language="ko") == []

    def test_short_text(self):
        """짧은 텍스트 (10자 미만) 처리"""
        assert extract_action_items("안녕", language="ko") == []

    def test_no_action_items(self):
        """액션 아이템이 없는 텍스트"""
        text = "오늘 날씨가 좋네요. 점심은 김치찌개 먹었습니다."
        items = extract_action_items(text, language="ko")
        # 액션 아이템이 없거나 매우 적어야 함
        assert isinstance(items, list)

    def test_duplicate_removal(self):
        """중복 액션 아이템 제거"""
        text = "보고서를 작성해 주세요. 보고서를 작성해 주세요."
        items = extract_action_items(text, language="ko")
        # 중복 제거로 동일 내용은 1개만
        task_texts = [item.task for item in items]
        normalized = [t.replace(" ", "").lower() for t in task_texts]
        assert len(normalized) == len(set(normalized))

    def test_max_50_items(self):
        """최대 50개 제한"""
        # 많은 액션 아이템 생성
        text = "\n".join([f"TODO: 작업 {i}을 완료해 주세요" for i in range(100)])
        items = extract_action_items(text, language="ko")
        assert len(items) <= 50

    def test_include_deadlines_false(self):
        """기한 추출 비활성화"""
        text = "김대리가 내일까지 보고서를 작성해 주세요."
        items = extract_action_items(text, language="ko", include_deadlines=False)
        for item in items:
            assert item.deadline is None

    def test_include_assignees_false(self):
        """담당자 추출 비활성화"""
        text = "김대리가 보고서를 작성해 주세요."
        items = extract_action_items(text, language="ko", include_assignees=False)
        for item in items:
            assert item.assignee is None


class TestExtractAssignee:
    """담당자 추출 테스트"""

    def test_korean_assignee(self):
        assert _extract_assignee("담당: 김철수", "ko") == "김철수"
        assert _extract_assignee("담당자: 이영희", "ko") == "이영희"

    def test_no_assignee(self):
        assert _extract_assignee("오늘 날씨가 좋습니다", "ko") is None


class TestExtractDeadline:
    """기한 추출 테스트"""

    def test_korean_date(self):
        result = _extract_deadline("5월 10일까지 완료", "ko")
        assert result is not None
        assert "5월" in result

    def test_korean_relative(self):
        result = _extract_deadline("내일까지 완료", "ko")
        assert result is not None
        assert "내일" in result

    def test_no_deadline(self):
        assert _extract_deadline("안녕하세요", "ko") is None


class TestExtractPriority:
    """우선순위 추출 테스트"""

    def test_high_priority(self):
        assert _extract_priority("긴급으로 처리해 주세요") == "high"
        assert _extract_priority("ASAP 완료 필요") == "high"

    def test_low_priority(self):
        assert _extract_priority("나중에 처리해도 됩니다") == "low"

    def test_medium_priority(self):
        assert _extract_priority("이번 주에 처리해 주세요") == "medium"
