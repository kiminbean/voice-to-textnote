"""
json_helpers 유틸리티 테스트
"""

from backend.utils.json_helpers import strip_json_comments


class TestStripJsonComments:
    """JSON 주석 제거 테스트"""

    def test_removes_line_comment(self):
        result = strip_json_comments('{"a": 1 // comment')
        assert result == '{"a": 1'

    def test_preserves_comment_inside_string(self):
        # 문자열 내부의 // 는 보호되어야 함
        result = strip_json_comments('{"url": "https://example.com"}')
        assert result == '{"url": "https://example.com"}'

    def test_handles_empty_string(self):
        result = strip_json_comments("")
        assert result == ""

    def test_no_comments(self):
        text = '{"a": 1, "b": 2}'
        assert strip_json_comments(text) == text

    def test_multiple_lines(self):
        text = '{\n  "a": 1, // 첫 줄\n  "b": 2  // 두 번째 줄\n}'
        result = strip_json_comments(text)
        assert "//" not in result.split("\n")[1]
        assert "//" not in result.split("\n")[2]

    def test_escaped_quote_before_comment(self):
        # 이스케이프 따옴표 뒤의 // 처리 (lines 29-30 커버)
        result = strip_json_comments(r'{"a": "hello \" // not comment"}')
        # \" 뒤의 // 는 문자열 안이므로 보호
        assert "// not comment" in result

    def test_escaped_backslash_in_string(self):
        # 이스케이프 백슬래시 (lines 29-30 커버)
        result = strip_json_comments(r'{"a": "path\\", "b": 1 // real comment')
        assert '"b": 1' in result
        assert "real comment" not in result

    def test_comment_at_end_of_line_with_trailing_space(self):
        result = strip_json_comments('  "key": "val"   // comment   ')
        assert result.rstrip() == '  "key": "val"'
