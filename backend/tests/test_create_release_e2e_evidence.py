from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_create_evidence_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "client/scripts/create_release_e2e_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("create_release_e2e_evidence", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_release_readiness_module():
    script_path = Path(__file__).resolve().parents[2] / "client/scripts/verify_release_readiness.py"
    spec = importlib.util.spec_from_file_location("verify_release_readiness", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_e2e_scaffold_contains_every_required_scenario(monkeypatch):
    create = load_create_evidence_module()
    readiness = load_release_readiness_module()
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    evidence = create.build_evidence(
        Path(__file__).resolve().parents[2],
        android_apk="app-debug.apk",
        ios_runner_app="Runner.app",
    )

    assert evidence["devices"]["android"]["serial"] == "android-serial"
    assert evidence["devices"]["ios"]["udid"] == "ios-udid"
    assert set(evidence["scenarios"]) == set(readiness.REQUIRED_E2E_SCENARIOS)
    assert all(scenario["pass"] is False for scenario in evidence["scenarios"].values())


def test_release_e2e_scaffold_round_trips_json(tmp_path):
    create = load_create_evidence_module()
    evidence = create.build_evidence(
        Path(__file__).resolve().parents[2],
        android_apk="app-debug.apk",
        ios_runner_app="Runner.app",
    )
    path = tmp_path / "release-e2e-evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["artifacts"]["android_apk"] == "app-debug.apk"
    assert loaded["artifacts"]["ios_runner_app"] == "Runner.app"
