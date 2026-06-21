from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dockerfile_lines() -> list[str]:
    return (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()


def test_dockerfile_copies_backend_before_installing_project():
    lines = dockerfile_lines()
    backend_copy = lines.index("COPY backend/ backend/")
    pip_install = next(index for index, line in enumerate(lines) if "pip install --no-cache-dir ." in line)

    assert backend_copy < pip_install


def test_dockerfile_does_not_copy_ignored_storage_directory():
    dockerfile = "\n".join(dockerfile_lines())
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "storage/" in dockerignore
    assert "COPY storage/" not in dockerfile
    assert "mkdir -p storage/temp storage/results" in dockerfile
