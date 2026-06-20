from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_release_readiness_module():
    script_path = Path(__file__).resolve().parents[2] / "client/scripts/verify_release_readiness.py"
    spec = importlib.util.spec_from_file_location("verify_release_readiness", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_evidence(tmp_path: Path, module) -> dict[str, object]:
    android_apk = tmp_path / "app-debug.apk"
    ios_runner = tmp_path / "Runner.app"
    android_apk.write_text("apk", encoding="utf-8")
    ios_runner.mkdir()

    return {
        "tested_at": "2026-06-15T09:00:00+09:00",
        "tester": "release-operator",
        "backend_version": "git:test",
        "client_version": "git:test",
        "devices": {
            "android": {
                "serial": "android-serial",
                "model": "Pixel 8",
                "os_version": "Android 16",
            },
            "ios": {
                "udid": "ios-udid",
                "model": "iPhone 15 Pro",
                "os_version": "iOS 18",
            },
        },
        "artifacts": {
            "android_apk": str(android_apk),
            "ios_runner_app": str(ios_runner),
        },
        "scenarios": {
            scenario: {
                "pass": True,
                "evidence": f"{label} verified on release test devices.",
            }
            for scenario, label in module.REQUIRED_E2E_SCENARIOS.items()
        },
    }


def write_evidence(tmp_path: Path, evidence: dict[str, object]) -> Path:
    evidence_path = tmp_path / "release-e2e-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return evidence_path


def write_tone_policy_files(root: Path, *, tone_model_line: str = 'tone_model: str = ""') -> None:
    (root / "backend/app").mkdir(parents=True)
    (root / "backend/app/config.py").write_text(tone_model_line, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "# opensmile은 AGPL-3.0",
                "# 로컬 전용 처리 환경에서만 사용",
                "# 네트워크 서비스 형태 외부 제공 금지",
                '"opensmile>=2.6.0",',
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "로컬 전용 처리 opensmile AGPL-3.0 네트워크 서비스 SaaS",
        encoding="utf-8",
    )


def write_readme_status(root: Path, content: str) -> None:
    (root / "README.md").write_text(content, encoding="utf-8")


def test_release_e2e_evidence_accepts_complete_manual_proof(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence_path = write_evidence(tmp_path, make_evidence(tmp_path, module))
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter)

    assert reporter.errors == []


def test_release_e2e_evidence_rejects_missing_required_scenario(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenarios.pop("push_deeplink_cold_start")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter)

    assert any("push_deeplink_cold_start" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_placeholder_scenario_evidence(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = "TODO: send an actual push notification on release devices"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter)

    assert any("placeholder evidence" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_device_id_mismatch(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence_path = write_evidence(tmp_path, make_evidence(tmp_path, module))
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "different-android")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter)

    assert any(
        "android device serial does not match strict env" in error for error in reporter.errors
    )


def test_release_e2e_example_lists_every_required_scenario():
    module = load_release_readiness_module()
    example_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    scenarios = example["scenarios"]

    assert set(scenarios) == set(module.REQUIRED_E2E_SCENARIOS)


def test_tone_release_policy_accepts_current_repo_policy():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_tone_release_policy(root, reporter)

    assert reporter.errors == []


def test_tone_release_policy_rejects_enabled_default(tmp_path):
    module = load_release_readiness_module()
    write_tone_policy_files(tmp_path, tone_model_line='tone_model: str = "egemaps-v2"')

    reporter = module.Reporter()
    module.check_tone_release_policy(tmp_path, reporter)

    assert any("default to disabled" in error for error in reporter.errors)


def test_tone_release_policy_rejects_missing_agpl_readme_warning(tmp_path):
    module = load_release_readiness_module()
    write_tone_policy_files(tmp_path)
    (tmp_path / "README.md").write_text("MIT License", encoding="utf-8")

    reporter = module.Reporter()
    module.check_tone_release_policy(tmp_path, reporter)

    assert any("README documents opensmile AGPL" in error for error in reporter.errors)


def test_readme_release_status_accepts_release_candidate_language(tmp_path):
    module = load_release_readiness_module()
    write_readme_status(
        tmp_path,
        "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH",
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert reporter.errors == []


def test_readme_release_status_rejects_production_ready_overclaim(tmp_path):
    module = load_release_readiness_module()
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 "
            "RELEASE_E2E_EVIDENCE_PATH Production Ready (31/31 SPECs 완료)"
        ),
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert any("must not claim Production Ready" in error for error in reporter.errors)


def test_mobile_workflow_exposes_manual_strict_release_gate():
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/mobile.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    required_snippets = [
        "workflow_dispatch:",
        "evidence_path:",
        "release-strict:",
        "Strict Release Readiness With Physical Devices",
        "- self-hosted",
        "- macOS",
        "- mobile-release",
        "environment: mobile-release",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "APNS_AUTH_KEY_P8",
        "APP_STORE_CONNECT_API_KEY_P8",
        "ANDROID_DEVICE_SERIAL",
        "IOS_DEVICE_UDID",
        "FIREBASE_TEST_DEVICE_TOKEN",
        "./scripts/verify_mobile.sh --native",
        "python3 client/scripts/verify_release_readiness.py --strict",
    ]

    for snippet in required_snippets:
        assert snippet in workflow
