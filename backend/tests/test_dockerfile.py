from __future__ import annotations

import tomllib
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


def test_linux_docker_build_skips_macos_only_mlx_dependencies():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    for package_name in ("mlx-whisper", "mlx"):
        dependency = next(dep for dep in dependencies if dep.startswith(f"{package_name}>="))
        assert "platform_system == 'Darwin'" in dependency
