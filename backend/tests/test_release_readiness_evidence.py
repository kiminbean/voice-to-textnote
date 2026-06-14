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
