from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dockerfile_lines() -> list[str]:
    return (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()


def production_compose_text() -> str:
    return (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")


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


def test_production_compose_forces_backend_production_environment():
    compose = production_compose_text()

    assert compose.count("- ENVIRONMENT=production") == 2
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}" in compose
    assert "--requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD is required}" in compose
    assert "- API_KEYS=${API_KEYS:?API_KEYS is required}" in compose
    assert "- OPENAI_API_KEY=${OPENAI_API_KEY:?OPENAI_API_KEY is required}" in compose


def test_production_compose_uses_internal_async_postgres_url():
    compose = production_compose_text()

    expected = (
        "DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-voicenote}:"
        "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@postgres:5432/"
        "${POSTGRES_DB:-voicenote}"
    )
    assert compose.count(expected) == 2
    assert "- DATABASE_URL=${DATABASE_URL}" not in compose
