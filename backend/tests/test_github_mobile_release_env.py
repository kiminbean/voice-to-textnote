from __future__ import annotations

import importlib.util
from pathlib import Path


def load_github_env_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_github_mobile_release_env.py"
    )
    spec = importlib.util.spec_from_file_location("verify_github_mobile_release_env", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_github_mobile_release_env_accepts_complete_snapshot():
    module = load_github_env_module()
    reporter = module.Reporter()

    module.check_snapshot(
        environments={module.ENVIRONMENT},
        runners=[
            {
                "labels": [
                    {"name": "self-hosted"},
                    {"name": "macOS"},
                    {"name": "mobile-release"},
                ]
            }
        ],
        secrets=set(module.REQUIRED_SECRETS),
        variables=set(module.REQUIRED_VARIABLES),
        reporter=reporter,
    )

    assert reporter.errors == []


def test_github_mobile_release_env_rejects_missing_runner_labels():
    module = load_github_env_module()
    reporter = module.Reporter()

    module.check_snapshot(
        environments={module.ENVIRONMENT},
        runners=[{"labels": [{"name": "self-hosted"}, {"name": "macOS"}]}],
        secrets=set(module.REQUIRED_SECRETS),
        variables=set(module.REQUIRED_VARIABLES),
        reporter=reporter,
    )

    assert any("required labels" in error for error in reporter.errors)


def test_github_mobile_release_env_rejects_missing_secret_and_variable():
    module = load_github_env_module()
    reporter = module.Reporter()
    secrets = set(module.REQUIRED_SECRETS)
    secrets.remove("APNS_AUTH_KEY_P8")
    variables = set(module.REQUIRED_VARIABLES)
    variables.remove("IOS_DEVICE_UDID")

    module.check_snapshot(
        environments={module.ENVIRONMENT},
        runners=[
            {
                "labels": [
                    {"name": "self-hosted"},
                    {"name": "macOS"},
                    {"name": "mobile-release"},
                ]
            }
        ],
        secrets=secrets,
        variables=variables,
        reporter=reporter,
    )

    assert any("APNS_AUTH_KEY_P8" in error for error in reporter.errors)
    assert any("IOS_DEVICE_UDID" in error for error in reporter.errors)
