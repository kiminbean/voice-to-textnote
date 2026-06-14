from __future__ import annotations

import importlib.util
from pathlib import Path


def load_configure_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "client/scripts/configure_github_mobile_release_env.py"
    )
    spec = importlib.util.spec_from_file_location(
        "configure_github_mobile_release_env", script_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_release_env_reports_missing_values(monkeypatch):
    module = load_configure_module()
    for name in [*module.REQUIRED_VARIABLES, *module.REQUIRED_SECRETS]:
        monkeypatch.delenv(name, raising=False)

    missing = module.configure_from_environment("owner/repo", dry_run=True)

    assert set(missing) == set(module.REQUIRED_VARIABLES) | set(module.REQUIRED_SECRETS)


def test_configure_release_env_uses_all_provided_values(monkeypatch):
    module = load_configure_module()
    for name in [*module.REQUIRED_VARIABLES, *module.REQUIRED_SECRETS]:
        monkeypatch.setenv(name, f"value-for-{name}")

    missing = module.configure_from_environment("owner/repo", dry_run=True)

    assert missing == []


def test_configure_release_env_uses_same_required_names_as_verifier():
    configure = load_configure_module()
    verifier_path = (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_github_mobile_release_env.py"
    )
    spec = importlib.util.spec_from_file_location("verify_github_mobile_release_env", verifier_path)
    assert spec is not None
    assert spec.loader is not None
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)

    assert set(configure.REQUIRED_SECRETS) == set(verifier.REQUIRED_SECRETS)
    assert set(configure.REQUIRED_VARIABLES) == set(verifier.REQUIRED_VARIABLES)
    assert configure.ENVIRONMENT == verifier.ENVIRONMENT
