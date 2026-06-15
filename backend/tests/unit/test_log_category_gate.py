"""
SPEC-BUGFIX-002 REQ-BF2-006: 운영 로그 category 필드 검증.

DB fallback 및 Redis fallback 로그가 structured logging category 필드를
포함하는지 확인하여 모니터링 대시보드에서 수집/알림할 수 있도록 한다.
"""
import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKER_TASKS_DIR = BACKEND_ROOT / "workers" / "tasks"
TRANSCRIPTION_API = BACKEND_ROOT / "app" / "api" / "v1" / "transcription" / "transcription.py"


def _function_has_db_fallback_log_without_category(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """DB fallback 로그 호출에 category 필드가 없으면 True."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr == "warning":
                has_db_fallback_msg = False
                has_category = False
                for arg in child.args:
                    if (
                        isinstance(arg, ast.Constant)
                        and isinstance(arg.value, str)
                        and "DB 결과 저장 실패" in arg.value
                    ):
                        has_db_fallback_msg = True
                for kw in child.keywords:
                    if kw.arg == "category":
                        has_category = True
                    if (
                        isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and "DB 결과 저장 실패" in kw.value.value
                    ):
                        has_db_fallback_msg = True
                if has_db_fallback_msg and not has_category:
                    return True
    return False


class TestLogCategoryField:
    """워커 태스크의 DB fallback 로그에 category 필드 포함 여부."""

    @pytest.mark.parametrize(
        "task_file",
        [
            "transcription_task.py",
            "diarization_task.py",
            "minutes_task.py",
            "summary_task.py",
            "sentiment_task.py",
        ],
    )
    def test_db_fallback_log_has_category(self, task_file: str):
        f = WORKER_TASKS_DIR / task_file
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                assert not _function_has_db_fallback_log_without_category(node), (
                    f"{task_file}::{node.name}의 DB fallback 로그에 category 필드가 없습니다. "
                    f"REQ-BF2-006: logger.warning(..., category=\"db_fallback\") 추가 필요."
                )

    def test_redis_fallback_log_has_category(self):
        source = TRANSCRIPTION_API.read_text(encoding="utf-8")
        assert 'category="redis_fallback"' in source, (
            "transcription.py의 Redis fallback 로그에 category 필드가 없습니다."
        )
