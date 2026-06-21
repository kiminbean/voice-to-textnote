from __future__ import annotations

from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_uses_current_backend_asgi_entrypoint():
    readme = readme_text()

    assert "uvicorn backend.app.main:app" in readme
    assert "uvicorn app.main:app" not in readme


def test_readme_does_not_document_removed_manual_init_db_command():
    readme = readme_text()

    assert "from app.db.sync_engine import init_db" not in readme
    assert "from backend.db.sync_engine import init_db" not in readme
    assert "validate_startup()" in readme
