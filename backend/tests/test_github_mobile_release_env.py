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
                ],
                "status": "online",
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


def test_github_mobile_release_env_rejects_offline_release_runner():
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
                ],
                "status": "offline",
            }
        ],
        secrets=set(module.REQUIRED_SECRETS),
        variables=set(module.REQUIRED_VARIABLES),
        reporter=reporter,
    )

    assert any("online" in error for error in reporter.errors)


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
                ],
                "status": "online",
            }
        ],
        secrets=secrets,
        variables=variables,
        reporter=reporter,
    )

    assert any("APNS_AUTH_KEY_P8" in error for error in reporter.errors)
    assert any("IOS_DEVICE_UDID" in error for error in reporter.errors)


def test_mobile_workflow_matches_github_release_env_contract():
    module = load_github_env_module()
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/mobile.yml"
    ).read_text(encoding="utf-8")

    assert f"environment: {module.ENVIRONMENT}" in workflow
    assert all(label in workflow for label in module.REQUIRED_RUNNER_LABELS)
    assert all(f"secrets.{secret}" in workflow for secret in module.REQUIRED_SECRETS)
    assert all(f"vars.{variable}" in workflow for variable in module.REQUIRED_VARIABLES)
    assert "python3 client/scripts/verify_mobile_release_runner.py" in workflow
    assert (
        workflow.index("python3 client/scripts/verify_mobile_release_runner.py")
        < workflow.index("./scripts/verify_mobile.sh --native")
        < workflow.index("python3 client/scripts/verify_release_readiness.py --strict")
    )


def test_mobile_workflow_verifies_ci_build_artifacts():
    workflow = (
        Path(__file__).resolve().parents[2] / ".github/workflows/mobile.yml"
    ).read_text(encoding="utf-8")

    assert "Verify Android release APK artifact" in workflow
    assert "test -s build/app/outputs/flutter-apk/app-release.apk" in workflow
    assert "Verify iOS no-codesign app artifact" in workflow
    assert "test -d build/ios/iphoneos/Runner.app" in workflow
    assert "test -s build/ios/iphoneos/Runner.app/Info.plist" in workflow
    assert workflow.index("flutter build apk --release") < workflow.index(
        "test -s build/app/outputs/flutter-apk/app-release.apk"
    )
    assert workflow.index("flutter build ios --debug --no-codesign") < workflow.index(
        "test -d build/ios/iphoneos/Runner.app"
    )
