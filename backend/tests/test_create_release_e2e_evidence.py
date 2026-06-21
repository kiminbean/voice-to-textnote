from __future__ import annotations

import importlib.util
import json
import plistlib
import zipfile
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
    assert set(evidence["artifact_sha256"]) == {"android_apk", "ios_runner_app"}


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
    assert set(loaded["artifact_sha256"]) == {"android_apk", "ios_runner_app"}


def test_release_e2e_evidence_artifacts_are_resolved_from_repo_root(
    monkeypatch, tmp_path
):
    readiness = load_release_readiness_module()
    root = tmp_path / "repo"
    android_apk = root / "client/build/app/outputs/flutter-apk/app-debug.apk"
    ios_runner_app = root / "client/build/ios/iphoneos/Runner.app"
    android_apk.parent.mkdir(parents=True)
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
    ios_runner_app.mkdir(parents=True)
    with (ios_runner_app / "Info.plist").open("wb") as plist:
        plistlib.dump(
            {
                "CFBundleIdentifier": "com.voicetextnote.app",
                "CFBundleExecutable": "Runner",
            },
            plist,
        )
    (ios_runner_app / "Runner").write_bytes(b"binary")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "tested_at": "2026-06-21T00:00:00+00:00",
                "tester": "release-operator",
                "backend_version": "git:abcdef1",
                "client_version": "git:abcdef1",
                "devices": {
                    "android": {
                        "serial": "android-serial",
                        "model": "Pixel 8",
                        "os_version": "Android 16",
                    },
                    "ios": {
                        "udid": "ios-udid",
                        "model": "iPhone 15",
                        "os_version": "iOS 18",
                    },
                },
                "artifacts": {
                    "android_apk": "client/build/app/outputs/flutter-apk/app-debug.apk",
                    "ios_runner_app": "client/build/ios/iphoneos/Runner.app",
                },
                "artifact_sha256": {
                    "android_apk": readiness.release_artifact_sha256(android_apk),
                    "ios_runner_app": readiness.release_artifact_sha256(ios_runner_app),
                },
                "scenarios": {
                    key: {
                        "pass": True,
                        "evidence": f"Observed physical-device pass for {key}.",
                    }
                    for key in readiness.REQUIRED_E2E_SCENARIOS
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.chdir(tmp_path)
    reporter = readiness.Reporter()

    readiness.check_release_e2e_evidence(evidence_path, reporter, root)

    assert reporter.errors == []
