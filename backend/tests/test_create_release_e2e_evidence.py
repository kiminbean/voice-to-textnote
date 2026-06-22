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


def write_release_artifacts(root: Path) -> tuple[Path, Path]:
    android_apk = root / "client/build/app/outputs/flutter-apk/app-release.apk"
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
    return android_apk, ios_runner_app


def write_ios_release_entitlements(path: Path) -> None:
    with path.open("wb") as plist:
        plistlib.dump(
            {
                "aps-environment": "production",
                "get-task-allow": False,
                "com.apple.developer.team-identifier": "KLMNOPQRST",
                "application-identifier": "KLMNOPQRST.com.voicetextnote.app",
            },
            plist,
        )


def test_release_e2e_scaffold_contains_every_required_scenario(monkeypatch, tmp_path):
    create = load_create_evidence_module()
    readiness = load_release_readiness_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    entitlements_path = tmp_path / "ios-release-entitlements.plist"
    write_ios_release_entitlements(entitlements_path)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.setenv("REQUIRE_ANDROID_RELEASE_SIGNING", "true")
    monkeypatch.setenv("IOS_RELEASE_ENTITLEMENTS_PATH", entitlements_path.name)

    evidence = create.build_evidence(
        tmp_path,
        android_apk=android_apk.relative_to(tmp_path).as_posix(),
        ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
    )

    assert evidence["devices"]["android"]["serial"] == "android-serial"
    assert evidence["devices"]["ios"]["udid"] == "ios-udid"
    assert evidence["release_gate"] == {
        "android_release_signing": True,
        "ios_production_entitlements": True,
        "ios_entitlements_sha256": readiness.release_artifact_sha256(entitlements_path),
    }
    assert set(evidence["scenarios"]) == set(readiness.REQUIRED_E2E_SCENARIOS)
    assert all(scenario["pass"] is False for scenario in evidence["scenarios"].values())
    assert {
        key: tuple(value["platforms"])
        for key, value in evidence["scenarios"].items()
    } == readiness.REQUIRED_E2E_SCENARIO_PLATFORMS
    assert set(evidence["artifact_sha256"]) == {"android_apk", "ios_runner_app"}


def test_release_e2e_scaffold_records_release_gate_state_from_env(tmp_path, monkeypatch):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    monkeypatch.delenv("REQUIRE_ANDROID_RELEASE_SIGNING", raising=False)
    monkeypatch.delenv("IOS_RELEASE_ENTITLEMENTS_PATH", raising=False)

    evidence = create.build_evidence(
        tmp_path,
        android_apk=android_apk.relative_to(tmp_path).as_posix(),
        ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
    )

    assert evidence["release_gate"] == {
        "android_release_signing": False,
        "ios_production_entitlements": False,
        "ios_entitlements_sha256": "",
    }


def test_release_e2e_scaffold_round_trips_json(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    evidence = create.build_evidence(
        tmp_path,
        android_apk=android_apk.relative_to(tmp_path).as_posix(),
        ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
    )
    path = tmp_path / "release-e2e-evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded["artifacts"]["android_apk"] == android_apk.relative_to(tmp_path).as_posix()
    assert loaded["artifacts"]["ios_runner_app"] == ios_runner_app.relative_to(tmp_path).as_posix()
    assert set(loaded["artifact_sha256"]) == {"android_apk", "ios_runner_app"}


def test_release_e2e_scaffold_output_resolves_from_repo_root(tmp_path):
    create = load_create_evidence_module()
    root = tmp_path / "repo"
    root.mkdir()

    output_path = create.resolve_output_path(root, "docs/release-e2e-evidence.json")

    assert output_path == root / "docs/release-e2e-evidence.json"


def test_release_e2e_scaffold_rejects_output_outside_repo(tmp_path):
    create = load_create_evidence_module()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()

    try:
        create.resolve_output_path(root, str(outside / "release-e2e-evidence.json"))
    except ValueError as exc:
        assert "output path must stay inside repo" in str(exc)
    else:
        raise AssertionError("resolve_output_path should reject output outside repo")


def test_release_e2e_scaffold_rejects_missing_artifacts(tmp_path):
    create = load_create_evidence_module()

    try:
        create.build_evidence(
            tmp_path,
            android_apk="missing.apk",
            ios_runner_app="Missing.app",
        )
    except ValueError as exc:
        assert "missing release artifact" in str(exc)
    else:
        raise AssertionError("build_evidence should reject missing release artifacts")


def test_release_e2e_scaffold_rejects_artifacts_outside_repo(tmp_path):
    create = load_create_evidence_module()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    android_apk, ios_runner_app = write_release_artifacts(outside)

    try:
        create.build_evidence(
            root,
            android_apk=str(android_apk),
            ios_runner_app=str(ios_runner_app),
        )
    except ValueError as exc:
        assert "must stay inside repo" in str(exc)
    else:
        raise AssertionError("build_evidence should reject artifacts outside repo")


def test_release_e2e_scaffold_rejects_absolute_artifact_inside_repo(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)

    try:
        create.build_evidence(
            tmp_path,
            android_apk=str(android_apk),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "repo-relative" in str(exc)
    else:
        raise AssertionError("build_evidence should reject absolute artifact paths")


def test_release_e2e_scaffold_rejects_non_default_artifact_path(tmp_path):
    create = load_create_evidence_module()
    _, ios_runner_app = write_release_artifacts(tmp_path)
    custom_apk = tmp_path / "custom-release.apk"
    with zipfile.ZipFile(custom_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")

    try:
        create.build_evidence(
            tmp_path,
            android_apk=custom_apk.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "canonical release output" in str(exc)
    else:
        raise AssertionError("build_evidence should reject non-default artifact paths")


def test_release_e2e_scaffold_rejects_invalid_android_apk(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    android_apk.write_text("not a zip apk", encoding="utf-8")

    try:
        create.build_evidence(
            tmp_path,
            android_apk=android_apk.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "valid APK zip" in str(exc)
    else:
        raise AssertionError("build_evidence should reject invalid APK artifacts")


def test_release_e2e_scaffold_rejects_android_artifact_without_apk_suffix(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    android_text = tmp_path / "app-release.txt"
    android_apk.rename(android_text)

    try:
        create.build_evidence(
            tmp_path,
            android_apk=android_text.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "must end with .apk" in str(exc)
    else:
        raise AssertionError("build_evidence should reject non-.apk artifacts")


def test_release_e2e_scaffold_rejects_android_debug_artifact(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    android_debug_apk = tmp_path / "app-debug.apk"
    android_apk.rename(android_debug_apk)

    try:
        create.build_evidence(
            tmp_path,
            android_apk=android_debug_apk.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "release APK" in str(exc)
    else:
        raise AssertionError("build_evidence should reject debug Android artifacts")


def test_release_e2e_scaffold_rejects_invalid_ios_runner_app(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    (ios_runner_app / "Runner").unlink()

    try:
        create.build_evidence(
            tmp_path,
            android_apk=android_apk.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_runner_app.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "missing executable" in str(exc)
    else:
        raise AssertionError("build_evidence should reject invalid iOS app artifacts")


def test_release_e2e_scaffold_rejects_ios_artifact_without_app_suffix(tmp_path):
    create = load_create_evidence_module()
    android_apk, ios_runner_app = write_release_artifacts(tmp_path)
    ios_bundle = tmp_path / "Runner.bundle"
    ios_runner_app.rename(ios_bundle)

    try:
        create.build_evidence(
            tmp_path,
            android_apk=android_apk.relative_to(tmp_path).as_posix(),
            ios_runner_app=ios_bundle.relative_to(tmp_path).as_posix(),
        )
    except ValueError as exc:
        assert "must end with .app" in str(exc)
    else:
        raise AssertionError("build_evidence should reject non-.app artifacts")


def test_release_e2e_evidence_artifacts_are_resolved_from_repo_root(
    monkeypatch, tmp_path
):
    readiness = load_release_readiness_module()
    root = tmp_path / "repo"
    android_apk = root / "client/build/app/outputs/flutter-apk/app-release.apk"
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
                "release_gate": {
                    "android_release_signing": True,
                    "ios_production_entitlements": True,
                    "ios_entitlements_sha256": "0" * 64,
                },
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
                    "android_apk": "client/build/app/outputs/flutter-apk/app-release.apk",
                    "ios_runner_app": "client/build/ios/iphoneos/Runner.app",
                },
                "artifact_sha256": {
                    "android_apk": readiness.release_artifact_sha256(android_apk),
                    "ios_runner_app": readiness.release_artifact_sha256(ios_runner_app),
                },
                "scenarios": {
                    key: {
                        "pass": True,
                        "platforms": list(readiness.REQUIRED_E2E_SCENARIO_PLATFORMS[key]),
                        "evidence": (
                            f"Observed physical-device pass for {key} on "
                            + ", ".join(
                                {
                                    "android": "android-serial",
                                    "ios": "ios-udid",
                                }[platform]
                                for platform in readiness.REQUIRED_E2E_SCENARIO_PLATFORMS[key]
                            )
                            + "."
                        ),
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
