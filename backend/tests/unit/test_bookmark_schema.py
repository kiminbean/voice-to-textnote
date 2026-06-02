"""
SPEC-BOOKMARK-001: Bookmark Schema 테스트
커버되지 않은 라인을 위한 테스트

커버되지 않은 라인:
- 28, 31: validate_color - None 처리
- 58, 61, 63: validate_color - strip, empty check, match
"""

import pytest
from pydantic import ValidationError

from backend.schemas.bookmark import (
    BookmarkCreate,
    BookmarkUpdate,
)


# ---------------------------------------------------------------------------
# validate_color 테스트
# ---------------------------------------------------------------------------


class TestBookmarkColorValidation:
    """북마크 색상 validation 테스트"""

    def test_validate_color_whitespace_returns_none(self) -> None:
        """공백 문자열은 None 반환 (라인 28, 31 커버)"""
        # BookmarkBase의 validate_color
        from backend.schemas.bookmark import BookmarkBase

        # 공백 문자열 -> None
        result = BookmarkBase.validate_color("   ")
        assert result is None

    def test_validate_color_update_whitespace_returns_none(self) -> None:
        """BookmarkUpdate에서도 공백 문자열은 None 반환 (라인 58, 61 커버)"""
        # BookmarkUpdate의 validate_color
        result = BookmarkUpdate.validate_color("   ")
        assert result is None

    def test_validate_color_invalid_format_raises_error(self) -> None:
        """잘못된 색상 형식 에러 (라인 63 커버)"""
        from backend.schemas.bookmark import BookmarkBase

        with pytest.raises(ValidationError) as exc_info:
            BookmarkBase(color="invalidcolor!")

        assert "color 는 #RRGGBB 형식 또는 3~20자 알파벳 색상명이어야 합니다" in str(exc_info.value)
