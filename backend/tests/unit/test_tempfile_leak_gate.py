"""
SPEC-BUGFIX-002 REQ-BF2-004: temp file/dir leak 정적 분석 게이트.

백엔드 프로덕션 코드에서 tempfile.mkdtemp/mkstemp를 사용하는 모든 함수는
같은 함수 범위 내에서 cleanup(unlink/rmtree)을 포함하거나,
출력 경로를 반환하여 caller가 cleanup을 담당하도록 설계되어야 한다.
누락 시 CI 실패.
"""
import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = [
    BACKEND_ROOT / "app" / "api",
    BACKEND_ROOT / "app" / "middleware",
    BACKEND_ROOT / "services",
    BACKEND_ROOT / "pipeline",
    BACKEND_ROOT / "workers",
    BACKEND_ROOT / "ml",
]

CLEANUP_NAMES = {"unlink", "rmtree", "rmdir", "remove", "_safe_unlink"}
TEMP_CREATE_NAMES = {"mkdtemp", "mkstemp", "NamedTemporaryFile"}


def _collect_python_files() -> list[Path]:
    result: list[Path] = []
    for src_dir in SOURCE_DIRS:
        result.extend(src_dir.rglob("*.py"))
    return [f for f in result if "__pycache__" not in str(f)]


def _function_has_tempfile_create(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr in TEMP_CREATE_NAMES:
                return True
            if isinstance(func, ast.Name) and func.id in TEMP_CREATE_NAMES:
                return True
    return False


def _function_has_cleanup(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in CLEANUP_NAMES:
            return True
        if isinstance(child, ast.Name) and child.id in CLEANUP_NAMES:
            return True
    return False


def _function_delegates_output(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """tempfile 경로를 caller에게 반환하여 cleanup 책임을 위임하는지 확인."""
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return True
    return False


def _find_tempfile_functions_without_cleanup() -> list[tuple[Path, str, int]]:
    """tempfile 생성 함수 중 cleanup도 없고 반환 위임도 없는 목록."""
    violations: list[tuple[Path, str, int]] = []
    for py_file in _collect_python_files():
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if _function_has_tempfile_create(node):
                    if not _function_has_cleanup(node) and not _function_delegates_output(node):
                        violations.append((py_file, node.name, node.lineno))
    return violations


class TestTempFileLeakGate:
    """tempfile 생성 호출은 대응하는 cleanup 경로를 포함해야 함."""

    def test_no_tempfile_leaks_in_production_code(self):
        violations = _find_tempfile_functions_without_cleanup()
        if violations:
            formatted = "\n".join(
                f"  {f.relative_to(BACKEND_ROOT)}:{line} in {name}"
                for f, name, line in violations
            )
            pytest.fail(
                f"tempfile 생성 함수에 cleanup(unlink/rmtree)이 없습니다:\n{formatted}\n"
                f"REQ-BF2-004: mkdtemp/mkstemp 사용 시 반드시 cleanup 경로를 포함하세요."
            )

    def test_gate_detects_intentional_leak(self):
        """게이트가 의도적 leak 코드를 감지하는지 확인 (self-test)."""
        source = """
import tempfile
def leaky_function():
    d = tempfile.mkdtemp()
    return d
"""
        tree = ast.parse(source)
        node = tree.body[1]
        assert isinstance(node, ast.FunctionDef)
        assert _function_has_tempfile_create(node)
        assert not _function_has_cleanup(node)
