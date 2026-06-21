from __future__ import annotations

from pathlib import Path


def workflow_text(name: str) -> str:
    return (Path(__file__).resolve().parents[2] / ".github/workflows" / name).read_text(
        encoding="utf-8"
    )


def test_backend_ci_enforces_lint_and_type_gates_for_release_scripts():
    workflow = workflow_text("ci.yml")

    assert "ruff check backend/ client/scripts" in workflow
    assert "mypy backend/ client/scripts --ignore-missing-imports" in workflow


def test_main_build_enforces_lint_and_type_gates_for_release_scripts():
    workflow = workflow_text("build.yml")

    assert "ruff check backend/ client/scripts" in workflow
    assert "mypy backend/ client/scripts --ignore-missing-imports" in workflow
