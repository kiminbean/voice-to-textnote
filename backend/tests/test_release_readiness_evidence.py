from __future__ import annotations

import importlib.util
import json
import plistlib
import shutil
import zipfile
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_release_readiness_module():
    script_path = Path(__file__).resolve().parents[2] / "client/scripts/verify_release_readiness.py"
    spec = importlib.util.spec_from_file_location("verify_release_readiness", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_evidence(tmp_path: Path, module) -> dict[str, object]:
    android_artifact_path = "client/build/app/outputs/flutter-apk/app-release.apk"
    ios_artifact_path = "client/build/ios/iphoneos/Runner.app"
    android_apk = tmp_path / android_artifact_path
    ios_runner = tmp_path / ios_artifact_path
    ios_entitlements = tmp_path / "ios-release-entitlements.plist"
    repo_root = Path(__file__).resolve().parents[2]
    current_revision = module.current_git_revision(repo_root)
    android_serial = "android-serial"
    ios_udid = "ios-udid"
    android_apk.parent.mkdir(parents=True)
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
        apk.writestr("META-INF/CERT.SF", "Signature-Version: 1.0\n")
        apk.writestr("META-INF/CERT.RSA", b"signature")
    ios_runner.mkdir(parents=True)
    write_ios_info_plist(ios_runner / "Info.plist")
    (ios_runner / "Runner").write_bytes(b"binary")
    write_ios_release_entitlements(ios_entitlements)

    return {
        "tested_at": datetime.now(UTC).isoformat(),
        "tester": "release-operator",
        "backend_version": current_revision,
        "client_version": current_revision,
        "release_gate": {
            "android_release_signing": True,
            "ios_production_entitlements": True,
            "ios_entitlements_sha256": module.release_artifact_sha256(ios_entitlements),
        },
        "devices": {
            "android": {
                "serial": android_serial,
                "model": "Pixel 8",
                "os_version": "Android 16",
            },
            "ios": {
                "udid": ios_udid,
                "model": "iPhone 15 Pro",
                "os_version": "iOS 18",
            },
        },
        "artifacts": {
            "android_apk": android_artifact_path,
            "ios_runner_app": ios_artifact_path,
        },
        "artifact_sha256": {
            "android_apk": module.release_artifact_sha256(android_apk),
            "ios_runner_app": module.release_artifact_sha256(ios_runner),
        },
        "scenarios": {
            scenario: {
                "pass": True,
                "platforms": list(module.REQUIRED_E2E_SCENARIO_PLATFORMS[scenario]),
                "evidence": (
                    f"{label} verified on release test devices: "
                    + ", ".join(
                        {
                            "android": android_serial,
                            "ios": ios_udid,
                        }[platform]
                        for platform in module.REQUIRED_E2E_SCENARIO_PLATFORMS[scenario]
                    )
                    + (
                        f". Screenshot release-e2e/{scenario}.png and device log "
                        f"release-e2e/{scenario}.log captured for this scenario."
                    )
                ),
            }
            for scenario, label in module.REQUIRED_E2E_SCENARIOS.items()
        },
    }


def write_ios_info_plist(
    path: Path,
    *,
    bundle_id: str = "com.voicetextnote.app",
    executable: str = "Runner",
) -> None:
    with path.open("wb") as plist:
        plistlib.dump(
            {"CFBundleIdentifier": bundle_id, "CFBundleExecutable": executable},
            plist,
        )


def write_ios_release_entitlements(
    path: Path,
    *,
    aps_environment: str = "production",
    get_task_allow: bool = False,
    team_id: str = "KLMNOPQRST",
) -> None:
    with path.open("wb") as plist:
        plistlib.dump(
            {
                "aps-environment": aps_environment,
                "get-task-allow": get_task_allow,
                "com.apple.developer.team-identifier": team_id,
                "application-identifier": f"{team_id}.com.voicetextnote.app",
            },
            plist,
        )


def write_evidence(tmp_path: Path, evidence: dict[str, object]) -> Path:
    evidence_path = tmp_path / "release-e2e-evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    return evidence_path


def resolve_evidence_artifact(root: Path, evidence: dict[str, object], key: str) -> Path:
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifact_path = artifacts[key]
    assert isinstance(artifact_path, str)
    return root / artifact_path


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
    (root / "README.md").write_text(
        (
            "3995 백엔드 테스트\n"
            "| 백엔드 단위/통합/E2E | 3995개 | 100.00% |\n"
            "| Flutter 테스트 | 415개 | - |\n"
            "| 총합 | 4410개 | - |\n"
            f"{content}"
        ),
        encoding="utf-8",
    )


def write_minimal_android_project(root: Path, *, target_sdk: int = 35) -> None:
    android_root = root / "client/android/app"
    (android_root / "src/main/kotlin/com/voicetextnote/app").mkdir(parents=True)
    (android_root / "src/main/res/xml").mkdir(parents=True)
    (android_root / "src/debug/res/xml").mkdir(parents=True)
    (android_root / "build.gradle").write_text(
        f"""
android {{
    namespace 'com.voicetextnote.app'
    compileSdk 36
    defaultConfig {{
        applicationId "com.voicetextnote.app"
        minSdkVersion 29
        targetSdkVersion {target_sdk}
    }}
}}
        """,
        encoding="utf-8",
    )
    (android_root / "src/main/AndroidManifest.xml").write_text(
        """
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
  <application android:networkSecurityConfig="@xml/network_security_config">
    <activity>
      <intent-filter>
        <action android:name="android.intent.action.SEND" />
        <data android:mimeType="text/plain" />
        <data android:mimeType="application/pdf" />
        <data android:mimeType="image/*" />
      </intent-filter>
    </activity>
  </application>
</manifest>
        """,
        encoding="utf-8",
    )
    (android_root / "src/main/kotlin/com/voicetextnote/app/MainActivity.kt").write_text(
        """
const val channel = "com.voicetextnote.app/shared_import"
fun consumeInitialSharedImport() {}
fun consumeLatestSharedImport() {}
val action = Intent.ACTION_SEND
val text = Intent.EXTRA_TEXT
val stream = Intent.EXTRA_STREAM
val display = OpenableColumns.DISPLAY_NAME
val payload = "filePath"
        """,
        encoding="utf-8",
    )
    (android_root / "src/main/res/xml/network_security_config.xml").write_text(
        '<network-security-config><base-config cleartextTrafficPermitted="false"></base-config></network-security-config>',
        encoding="utf-8",
    )
    (android_root / "src/debug/res/xml/network_security_config.xml").write_text(
        """
<network-security-config>
  <base-config cleartextTrafficPermitted="false"></base-config>
  <domain-config cleartextTrafficPermitted="true">
    <domain>localhost</domain>
    <domain>100.110.255.105</domain>
  </domain-config>
</network-security-config>
        """,
        encoding="utf-8",
    )


def write_minimal_ios_project(
    root: Path,
    *,
    deployment_target: str = "15.0",
    insecure_ats_exception: bool = False,
) -> None:
    ios_root = root / "client/ios/Runner"
    project_root = root / "client/ios/Runner.xcodeproj"
    ios_root.mkdir(parents=True)
    project_root.mkdir(parents=True)
    info_plist: dict[str, object] = {
        "UIBackgroundModes": ["audio", "remote-notification"],
        "CFBundleURLTypes": [
            {"CFBundleURLSchemes": ["voicetextnote"]},
        ],
        "CFBundleDocumentTypes": [
            {
                "LSItemContentTypes": [
                    "com.adobe.pdf",
                    "org.openxmlformats.wordprocessingml.document",
                    "public.image",
                ],
            },
        ],
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": False},
    }
    if insecure_ats_exception:
        info_plist["NSAppTransportSecurity"] = {
            "NSAllowsArbitraryLoads": False,
            "NSExceptionDomains": {
                "localhost": {"NSExceptionAllowsInsecureHTTPLoads": True},
            },
        }
    with (ios_root / "Info.plist").open("wb") as plist:
        plistlib.dump(info_plist, plist)
    with (ios_root / "Runner.entitlements").open("wb") as plist:
        plistlib.dump({"aps-environment": "production"}, plist)
    (project_root / "project.pbxproj").write_text(
        f"""
PRODUCT_BUNDLE_IDENTIFIER = com.voicetextnote.app;
DEVELOPMENT_TEAM = ABCDE12345;
IPHONEOS_DEPLOYMENT_TARGET = {deployment_target};
        """,
        encoding="utf-8",
    )
    (ios_root / "AppDelegate.swift").write_text(
        """
FlutterMethodChannel(
      name: channelName
)
private let channelName = "com.voicetextnote.app/recording"
method == "startBackgroundTask"
method == "stopBackgroundTask"
method == "flushRecording"
UIApplication.shared.beginBackgroundTask
UIApplication.shared.endBackgroundTask
AVAudioSession.interruptionNotification
AVAudioSession.routeChangeNotification
method: "onInterruptionBegin"
method: "onInterruptionEnd"
method: "onRouteChange"
private let sharedImportChannelName = "com.voicetextnote.app/shared_import"
consumeInitialSharedImport
consumeLatestSharedImport
override func application(
sharedImportPayload(from: url)
copySharedFile(_ url: URL)
case "png":
"filePath": target.path
        """,
        encoding="utf-8",
    )


def test_release_e2e_evidence_accepts_complete_manual_proof(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence_path = write_evidence(tmp_path, make_evidence(tmp_path, module))
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert reporter.errors == []


def test_release_e2e_evidence_rejects_unknown_top_level_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["legacy_report_url"] = "https://example.invalid/release-e2e"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "unknown top-level key: legacy_report_url" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_missing_release_gate(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence.pop("release_gate")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("missing release gate metadata" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unsigned_android_release_gate(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["release_gate"] = {
        "android_release_signing": False,
        "ios_production_entitlements": True,
    }
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "must record signed Android release gate" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_missing_ios_entitlement_gate(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["release_gate"] = {
        "android_release_signing": True,
        "ios_production_entitlements": False,
        "ios_entitlements_sha256": "0" * 64,
    }
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "must record production iOS entitlement gate" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_missing_ios_entitlement_hash(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    release_gate = evidence["release_gate"]
    assert isinstance(release_gate, dict)
    release_gate.pop("ios_entitlements_sha256")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "iOS entitlements hash must be a string" in error for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_invalid_ios_entitlement_hash(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    release_gate = evidence["release_gate"]
    assert isinstance(release_gate, dict)
    release_gate["ios_entitlements_sha256"] = "not-a-sha256"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "iOS entitlements hash must be lowercase SHA-256 hex" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_ios_entitlement_hash_mismatch(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    entitlements_path = tmp_path / "ios-release-entitlements.plist"
    write_ios_release_entitlements(entitlements_path, team_id="ZYXWVUTSRQ")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.setenv("IOS_RELEASE_ENTITLEMENTS_PATH", str(entitlements_path))

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "iOS entitlements hash mismatch" in error for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_unknown_release_gate_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    release_gate = evidence["release_gate"]
    assert isinstance(release_gate, dict)
    release_gate["legacy_signing_mode"] = "release"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "unknown release gate: legacy_signing_mode" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_unknown_device_platform(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    devices = evidence["devices"]
    assert isinstance(devices, dict)
    devices["web"] = {
        "serial": "browser-session",
        "model": "Chrome",
        "os_version": "macOS",
    }
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("unknown device platform: web" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unknown_device_metadata_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    devices = evidence["devices"]
    assert isinstance(devices, dict)
    android_device = devices["android"]
    assert isinstance(android_device, dict)
    android_device["legacy_fingerprint"] = "old-release-device"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "unknown android device metadata key: legacy_fingerprint" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_non_string_device_id(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    devices = evidence["devices"]
    assert isinstance(devices, dict)
    android_device = devices["android"]
    assert isinstance(android_device, dict)
    android_device["serial"] = 12345
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "12345")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("android device serial must be a string" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_placeholder_device_metadata(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    devices = evidence["devices"]
    assert isinstance(devices, dict)
    android_device = devices["android"]
    assert isinstance(android_device, dict)
    android_device["model"] = "TBD"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "android device model contains unresolved placeholder" in error
        for error in reporter.errors
    )


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
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("push_deeplink_cold_start" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unknown_scenario_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenarios["legacy_push_deeplink"] = {
        "pass": True,
        "evidence": "Legacy deeplink scenario verified before release.",
    }
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("unknown scenario" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unknown_scenario_result_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["manual_override"] = True
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "unknown scenario result key: push_stt_complete.manual_override" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_missing_scenario_platforms(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario.pop("platforms")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario platforms must be a non-empty list: push_stt_complete" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_platform_mismatch(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["platforms"] = ["android"]
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario platforms mismatch: push_stt_complete expected android,ios" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_duplicate_scenario_platforms(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["platforms"] = ["android", "android", "ios"]
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario platforms include duplicates: push_stt_complete (android)"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_unknown_scenario_platform(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["ios_release_http_blocked"]
    assert isinstance(scenario, dict)
    scenario["platforms"] = ["ios", "web"]
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario platforms include unknown platform: ios_release_http_blocked (web)"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_non_iso_test_timestamp(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["tested_at"] = "yesterday after the final device run"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("test timestamp must be ISO-8601" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_naive_test_timestamp(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["tested_at"] = datetime.now().replace(microsecond=0).isoformat()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "test timestamp must include timezone" in error for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_placeholder_tester(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["tester"] = "TODO"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("tester contains unresolved placeholder" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_future_test_timestamp(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["tested_at"] = "2099-01-01T00:00:00+00:00"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("test timestamp must not be in the future" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_stale_test_timestamp(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["tested_at"] = (datetime.now(UTC) - timedelta(days=15)).isoformat()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("test timestamp is stale" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_non_git_revision_versions(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["backend_version"] = "release candidate build"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("backend version must be git:<sha>" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_version_mismatch_with_current_git(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence["backend_version"] = "git:0000000"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter)

    assert any("backend version does not match current git revision" in error for error in reporter.errors)


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
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("placeholder evidence" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_too_short_scenario_evidence(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = "ok"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "evidence note is too short: push_stt_complete" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_duplicate_scenario_evidence(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    duplicate_note = (
        "Release E2E observation captured on android-serial and ios-udid with "
        "screenshot release-e2e/push_stt_complete.png, screenshot "
        "release-e2e/push_summary_complete.png, and log "
        "release-e2e/push_stt_complete-push_summary_complete.log attached for the "
        "physical release devices."
    )
    for key in ["push_stt_complete", "push_summary_complete"]:
        scenario = scenarios[key]
        assert isinstance(scenario, dict)
        scenario["evidence"] = duplicate_note
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence is duplicated: push_stt_complete, push_summary_complete"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_duplicate_observation_reference(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    first = scenarios["push_stt_complete"]
    second = scenarios["push_summary_complete"]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    first["evidence"] = (
        "STT completion observed on android-serial and ios-udid with screenshot "
        "release-e2e/push_stt_complete-push_summary_complete-shared.png and "
        "device log release-e2e/push_stt_complete.log."
    )
    second["evidence"] = (
        "Summary completion observed on android-serial and ios-udid with screenshot "
        "release-e2e/push_stt_complete-push_summary_complete-shared.png and "
        "device log release-e2e/push_summary_complete.log."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario observation artifact reference is duplicated: "
        "release-e2e/push_stt_complete-push_summary_complete-shared.png "
        "(push_stt_complete, push_summary_complete)"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_evidence_without_observation_artifact(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = (
        "STT completion was verified on release test devices android-serial and "
        "ios-udid with the expected notification behavior."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence missing observation artifact marker: push_stt_complete"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_evidence_without_observation_reference(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = (
        "STT completion was verified on release test devices android-serial and "
        "ios-udid with screenshot and device log captured."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence missing observation artifact reference: push_stt_complete"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_evidence_without_specific_reference(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = (
        "STT completion was verified on release test devices android-serial and "
        "ios-udid with screenshot release-e2e/push_summary_complete.png and "
        "device log release-e2e/push_summary_complete.log captured."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence missing scenario-specific observation artifact reference: "
        "push_stt_complete"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_non_string_scenario_evidence(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["push_stt_complete"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = 1234567890123456789012345
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence must be a string: push_stt_complete" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_evidence_without_android_device_id(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["android_release_cleartext_blocked"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = (
        "Android release HTTP blocked on a physical release device. "
        "Screenshot release-e2e/android_release_cleartext_blocked.png and device log "
        "release-e2e/android_release_cleartext_blocked.log captured."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence missing device id: android_release_cleartext_blocked (android)"
        in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_scenario_evidence_without_ios_device_id(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    scenarios = evidence["scenarios"]
    assert isinstance(scenarios, dict)
    scenario = scenarios["ios_release_http_blocked"]
    assert isinstance(scenario, dict)
    scenario["evidence"] = (
        "iOS release HTTP blocked on a physical release device. "
        "Screenshot release-e2e/ios_release_http_blocked.png and device log "
        "release-e2e/ios_release_http_blocked.log captured."
    )
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "scenario evidence missing device id: ios_release_http_blocked (ios)" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_device_id_mismatch(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence_path = write_evidence(tmp_path, make_evidence(tmp_path, module))
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "different-android")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "android device serial does not match strict env" in error for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_android_apk_directory(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    android_apk.unlink()
    android_apk.mkdir()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be a file: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_non_string_artifact_path(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = 12345
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact path must be a string: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_absolute_artifact_path_inside_repo(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = str(tmp_path / str(artifacts["android_apk"]))
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "artifact path must be repo-relative: android_apk" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_non_default_artifact_path(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    alternate_apk_path = "client/build/app/outputs/flutter-apk/custom-release.apk"
    alternate_apk = tmp_path / alternate_apk_path
    alternate_apk.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(alternate_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = alternate_apk_path
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(alternate_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "artifact path must match canonical release output: android_apk" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_missing_artifact_hashes(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    evidence.pop("artifact_sha256", None)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("missing artifact hashes" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_artifact_hash_mismatch(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = "0" * 64
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact hash mismatch: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_invalid_artifact_hash_format(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = "not-a-sha256"
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any(
        "artifact hash must be lowercase SHA-256 hex: android_apk" in error
        for error in reporter.errors
    )


def test_release_e2e_evidence_rejects_non_string_artifact_hash(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = 12345
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact hash must be a string: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unknown_artifact_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["legacy_ipa"] = str(tmp_path / "Legacy.ipa")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("unknown artifact: legacy_ipa" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unknown_artifact_hash_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["legacy_ipa"] = "0" * 64
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("unknown artifact hash: legacy_ipa" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_android_artifact_without_apk_suffix(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_artifact = tmp_path / "app-release.txt"
    android_artifact.write_text("not an apk", encoding="utf-8")
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = android_artifact.relative_to(tmp_path).as_posix()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact path must end with .apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_android_debug_artifact(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    android_debug_apk = tmp_path / "app-debug.apk"
    android_apk.rename(android_debug_apk)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = android_debug_apk.relative_to(tmp_path).as_posix()
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(android_debug_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be a release APK: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_android_artifact_path_traversal(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    android_apk = outside / "app-release.apk"
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = "../outside/app-release.apk"
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(android_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, root)

    assert any("artifact path must stay inside repo" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_absolute_artifact_outside_repo(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    android_apk = outside / "app-release.apk"
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["android_apk"] = str(android_apk)
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(android_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, root)

    assert any("artifact path must be repo-relative" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_empty_android_apk(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    android_apk.write_bytes(b"")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be non-empty: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_non_zip_android_apk(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    android_apk.write_text("not a zip apk", encoding="utf-8")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be a valid APK zip: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_android_apk_without_dex(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(android_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be a valid APK zip: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_unsigned_android_apk(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    android_apk = resolve_evidence_artifact(tmp_path, evidence, "android_apk")
    with zipfile.ZipFile(android_apk, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest />")
        apk.writestr("classes.dex", b"dex\n035\0")
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["android_apk"] = module.release_artifact_sha256(android_apk)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact must be signed: android_apk" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_ios_runner_without_info_plist(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    ios_runner = resolve_evidence_artifact(tmp_path, evidence, "ios_runner_app")
    (ios_runner / "Info.plist").unlink()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact missing Info.plist: ios_runner_app" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_ios_runner_bundle_id_mismatch(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    ios_runner = resolve_evidence_artifact(tmp_path, evidence, "ios_runner_app")
    write_ios_info_plist(ios_runner / "Info.plist", bundle_id="com.example.wrong")
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact bundle id mismatch: ios_runner_app" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_ios_runner_missing_executable(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    evidence = make_evidence(tmp_path, module)
    ios_runner = resolve_evidence_artifact(tmp_path, evidence, "ios_runner_app")
    (ios_runner / "Runner").unlink()
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, tmp_path)

    assert any("artifact missing executable: ios_runner_app" in error for error in reporter.errors)


def test_release_e2e_evidence_rejects_ios_artifact_path_traversal(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    ios_runner = outside / "Runner.app"
    ios_runner.mkdir(parents=True)
    write_ios_info_plist(ios_runner / "Info.plist")
    (ios_runner / "Runner").write_bytes(b"binary")
    evidence = make_evidence(tmp_path, module)
    artifacts = evidence["artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["ios_runner_app"] = "../outside/Runner.app"
    artifact_hashes = evidence["artifact_sha256"]
    assert isinstance(artifact_hashes, dict)
    artifact_hashes["ios_runner_app"] = module.release_artifact_sha256(ios_runner)
    evidence_path = write_evidence(tmp_path, evidence)
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")

    reporter = module.Reporter()
    module.check_release_e2e_evidence(evidence_path, reporter, root)

    assert any("artifact path must stay inside repo" in error for error in reporter.errors)


def test_strict_external_rejects_evidence_path_outside_repo(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    outside_evidence = tmp_path / "release-e2e-evidence.json"
    outside_evidence.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("REQUIRE_ANDROID_RELEASE_SIGNING", "true")
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(tmp_path / "firebase.json"))
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(tmp_path / "AuthKey_APNS.p8"))
    monkeypatch.setenv("APNS_KEY_ID", "ABCDEFGHIJ")
    monkeypatch.setenv("APNS_TEAM_ID", "KLMNOPQRST")
    monkeypatch.setenv("APP_STORE_CONNECT_API_KEY_PATH", str(tmp_path / "AuthKey_ASC.p8"))
    monkeypatch.setenv("APP_STORE_CONNECT_KEY_ID", "UVWXYZ1234")
    monkeypatch.setenv("APP_STORE_CONNECT_ISSUER_ID", "issuer-id")
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.setenv("IOS_RELEASE_ENTITLEMENTS_PATH", "docs/ios-release-entitlements.plist")
    monkeypatch.setenv("FIREBASE_TEST_DEVICE_TOKEN", "firebase-token")
    monkeypatch.setenv("RELEASE_E2E_EVIDENCE_PATH", str(outside_evidence))

    monkeypatch.setattr(module, "check_service_account", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_private_key_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_value", lambda *_args: None)
    monkeypatch.setattr(module, "require_android_device", lambda *_args: None)
    monkeypatch.setattr(module, "require_ios_device", lambda *_args: None)
    monkeypatch.setattr(module, "check_ios_release_entitlements", lambda *_args: None)

    def reject_unreachable_evidence_check(*_args):
        raise AssertionError("outside evidence must be rejected before JSON validation")

    monkeypatch.setattr(module, "check_release_e2e_evidence", reject_unreachable_evidence_check)

    reporter = module.Reporter()
    module.check_strict_external(reporter)

    assert "Release E2E evidence path must stay inside repo" in reporter.errors


def test_strict_private_key_file_rejects_invalid_pem(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    key_path = tmp_path / "AuthKey_APNS.p8"
    key_path.write_text("not a pem private key", encoding="utf-8")
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(key_path))

    reporter = module.Reporter()
    module.require_env_private_key_file(reporter, "APNS_AUTH_KEY_PATH", "APNs auth key")

    assert "APNs auth key: APNS_AUTH_KEY_PATH private key PEM is invalid" in reporter.errors


def test_strict_private_key_file_accepts_private_key_pem(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    key_path = tmp_path / "AuthKey_ASC.p8"
    key_path.write_text(
        "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_STORE_CONNECT_API_KEY_PATH", str(key_path))

    reporter = module.Reporter()
    module.require_env_private_key_file(
        reporter, "APP_STORE_CONNECT_API_KEY_PATH", "App Store Connect API key"
    )

    assert reporter.errors == []


def test_android_device_check_accepts_whitespace_separated_adb_device(monkeypatch):
    module = load_release_readiness_module()
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setattr(
        module,
        "read_command_output",
        lambda command: (
            0,
            "List of devices attached\nandroid-serial device product:pixel\n",
        ),
    )

    reporter = module.Reporter()
    module.require_android_device(reporter)

    assert reporter.errors == []


def test_firebase_service_account_rejects_non_object_json(tmp_path):
    module = load_release_readiness_module()
    service_account = tmp_path / "firebase.json"
    service_account.write_text("[]", encoding="utf-8")

    reporter = module.Reporter()
    module.check_service_account(service_account, reporter)

    assert "Firebase service account JSON must be an object" in reporter.errors


def test_firebase_service_account_rejects_incomplete_private_key(tmp_path):
    module = load_release_readiness_module()
    service_account = tmp_path / "firebase.json"
    service_account.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "voice-to-textnote",
                "private_key": "-----BEGIN PRIVATE KEY-----\nabc123\n",
                "client_email": "release@voice-to-textnote.iam.gserviceaccount.com",
            }
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_service_account(service_account, reporter)

    assert "Firebase service account private key missing" in reporter.errors


def test_firebase_service_account_rejects_non_string_private_key(tmp_path):
    module = load_release_readiness_module()
    service_account = tmp_path / "firebase.json"
    service_account.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "voice-to-textnote",
                "private_key": 12345,
                "client_email": "release@voice-to-textnote.iam.gserviceaccount.com",
            }
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_service_account(service_account, reporter)

    assert "Firebase service account private_key must be a string" in reporter.errors


def test_firebase_service_account_rejects_wrong_project_client_email(tmp_path):
    module = load_release_readiness_module()
    service_account = tmp_path / "firebase.json"
    service_account.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "voice-to-textnote",
                "private_key": (
                    "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----\n"
                ),
                "client_email": "release@other-project.iam.gserviceaccount.com",
            }
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_service_account(service_account, reporter)

    assert "Firebase service account client_email missing or invalid" in reporter.errors


def test_firebase_service_account_rejects_non_string_client_email(tmp_path):
    module = load_release_readiness_module()
    service_account = tmp_path / "firebase.json"
    service_account.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "voice-to-textnote",
                "private_key": (
                    "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----\n"
                ),
                "client_email": ["release@voice-to-textnote.iam.gserviceaccount.com"],
            }
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_service_account(service_account, reporter)

    assert "Firebase service account client_email must be a string" in reporter.errors


def test_strict_external_rejects_malformed_app_store_connect_issuer_id(monkeypatch):
    module = load_release_readiness_module()
    monkeypatch.setenv("APP_STORE_CONNECT_ISSUER_ID", "issuer-id")

    reporter = module.Reporter()
    module.require_env_value(
        reporter,
        "APP_STORE_CONNECT_ISSUER_ID",
        "App Store Connect issuer id",
        module.APP_STORE_CONNECT_ISSUER_ID_PATTERN,
    )

    assert (
        "App Store Connect issuer id: APP_STORE_CONNECT_ISSUER_ID does not match expected format"
        in reporter.errors
    )


def test_strict_external_accepts_uuid_app_store_connect_issuer_id(monkeypatch):
    module = load_release_readiness_module()
    monkeypatch.setenv(
        "APP_STORE_CONNECT_ISSUER_ID",
        "12345678-1234-1234-1234-123456789abc",
    )

    reporter = module.Reporter()
    module.require_env_value(
        reporter,
        "APP_STORE_CONNECT_ISSUER_ID",
        "App Store Connect issuer id",
        module.APP_STORE_CONNECT_ISSUER_ID_PATTERN,
    )

    assert reporter.errors == []


def test_strict_external_requires_android_release_signing_mode(monkeypatch):
    module = load_release_readiness_module()
    repo_root = Path(__file__).resolve().parents[2]

    monkeypatch.delenv("REQUIRE_ANDROID_RELEASE_SIGNING", raising=False)
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(repo_root / "firebase.json"))
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(repo_root / "AuthKey_APNS.p8"))
    monkeypatch.setenv("APNS_KEY_ID", "ABCDEFGHIJ")
    monkeypatch.setenv("APNS_TEAM_ID", "KLMNOPQRST")
    monkeypatch.setenv("APP_STORE_CONNECT_API_KEY_PATH", str(repo_root / "AuthKey_ASC.p8"))
    monkeypatch.setenv("APP_STORE_CONNECT_KEY_ID", "UVWXYZ1234")
    monkeypatch.setenv("APP_STORE_CONNECT_ISSUER_ID", "issuer-id")
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.setenv("IOS_RELEASE_ENTITLEMENTS_PATH", "docs/ios-release-entitlements.plist")
    monkeypatch.setenv("FIREBASE_TEST_DEVICE_TOKEN", "firebase-token")
    monkeypatch.setenv(
        "RELEASE_E2E_EVIDENCE_PATH",
        str(repo_root / "docs/release-e2e-evidence.example.json"),
    )

    monkeypatch.setattr(module, "check_service_account", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_private_key_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_android_device", lambda *_args: None)
    monkeypatch.setattr(module, "require_ios_device", lambda *_args: None)
    monkeypatch.setattr(module, "check_ios_release_entitlements", lambda *_args: None)
    monkeypatch.setattr(module, "check_release_e2e_evidence", lambda *_args: None)

    reporter = module.Reporter()
    module.check_strict_external(reporter)

    assert (
        "Android release signing gate: REQUIRE_ANDROID_RELEASE_SIGNING is not set"
        in reporter.errors
    )


def test_ios_release_entitlements_accepts_production_app_store_profile(
    tmp_path, monkeypatch
):
    module = load_release_readiness_module()
    entitlements_path = tmp_path / "ios-release-entitlements.plist"
    with entitlements_path.open("wb") as plist:
        plistlib.dump(
            {
                "aps-environment": "production",
                "get-task-allow": False,
                "com.apple.developer.team-identifier": "KLMNOPQRST",
                "application-identifier": "KLMNOPQRST.com.voicetextnote.app",
            },
            plist,
        )
    monkeypatch.setenv("APNS_TEAM_ID", "KLMNOPQRST")

    reporter = module.Reporter()
    module.check_ios_release_entitlements(entitlements_path, reporter)

    assert reporter.errors == []


def test_ios_release_entitlements_rejects_development_profile(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    entitlements_path = tmp_path / "ios-release-entitlements.plist"
    with entitlements_path.open("wb") as plist:
        plistlib.dump(
            {
                "aps-environment": "development",
                "get-task-allow": True,
                "com.apple.developer.team-identifier": "KLMNOPQRST",
                "application-identifier": "KLMNOPQRST.com.voicetextnote.app",
            },
            plist,
        )
    monkeypatch.setenv("APNS_TEAM_ID", "KLMNOPQRST")

    reporter = module.Reporter()
    module.check_ios_release_entitlements(entitlements_path, reporter)

    assert "iOS release entitlements must use production APNs environment" in reporter.errors
    assert "iOS release entitlements must set get-task-allow to false" in reporter.errors


def test_strict_external_requires_ios_release_entitlements(monkeypatch):
    module = load_release_readiness_module()
    repo_root = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("REQUIRE_ANDROID_RELEASE_SIGNING", "true")
    monkeypatch.setenv("FIREBASE_CREDENTIALS_PATH", str(repo_root / "firebase.json"))
    monkeypatch.setenv("APNS_AUTH_KEY_PATH", str(repo_root / "AuthKey_APNS.p8"))
    monkeypatch.setenv("APNS_KEY_ID", "ABCDEFGHIJ")
    monkeypatch.setenv("APNS_TEAM_ID", "KLMNOPQRST")
    monkeypatch.setenv("APP_STORE_CONNECT_API_KEY_PATH", str(repo_root / "AuthKey_ASC.p8"))
    monkeypatch.setenv("APP_STORE_CONNECT_KEY_ID", "UVWXYZ1234")
    monkeypatch.setenv("APP_STORE_CONNECT_ISSUER_ID", "issuer-id")
    monkeypatch.setenv("ANDROID_DEVICE_SERIAL", "android-serial")
    monkeypatch.setenv("IOS_DEVICE_UDID", "ios-udid")
    monkeypatch.delenv("IOS_RELEASE_ENTITLEMENTS_PATH", raising=False)
    monkeypatch.setenv("FIREBASE_TEST_DEVICE_TOKEN", "firebase-token")
    monkeypatch.setenv(
        "RELEASE_E2E_EVIDENCE_PATH",
        str(repo_root / "docs/release-e2e-evidence.example.json"),
    )

    monkeypatch.setattr(module, "check_service_account", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_private_key_file", lambda *_args: None)
    monkeypatch.setattr(module, "require_env_value", lambda *_args: None)
    monkeypatch.setattr(module, "require_android_device", lambda *_args: None)
    monkeypatch.setattr(module, "require_ios_device", lambda *_args: None)
    monkeypatch.setattr(module, "check_release_e2e_evidence", lambda *_args: None)

    reporter = module.Reporter()
    module.check_strict_external(reporter)

    assert (
        "iOS release entitlements evidence: IOS_RELEASE_ENTITLEMENTS_PATH is not set"
        in reporter.errors
    )


def test_release_e2e_example_lists_every_required_scenario():
    module = load_release_readiness_module()
    example_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    scenarios = example["scenarios"]

    assert set(scenarios) == set(module.REQUIRED_E2E_SCENARIOS)
    assert {
        key: tuple(value["platforms"])
        for key, value in scenarios.items()
    } == module.REQUIRED_E2E_SCENARIO_PLATFORMS


def test_release_e2e_example_matches_strict_top_level_schema():
    example_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))

    assert set(example) == {
        "tested_at",
        "tester",
        "backend_version",
        "client_version",
        "release_gate",
        "devices",
        "artifacts",
        "artifact_sha256",
        "scenarios",
    }
    assert example["release_gate"] == {
        "android_release_signing": True,
        "ios_production_entitlements": True,
        "ios_entitlements_sha256": "0" * 64,
    }
    assert set(example["artifact_sha256"]) == set(example["artifacts"])


def test_release_e2e_example_uses_release_android_artifact_path():
    example_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.example.json"
    example = json.loads(example_path.read_text(encoding="utf-8"))

    assert example["artifacts"]["android_apk"].endswith("app-release.apk")


def test_tracked_release_e2e_scaffold_lists_every_required_scenario():
    module = load_release_readiness_module()
    scaffold_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.json"
    scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))
    scenarios = scaffold["scenarios"]

    assert set(scenarios) == set(module.REQUIRED_E2E_SCENARIOS)
    assert {
        key: tuple(value["platforms"])
        for key, value in scenarios.items()
    } == module.REQUIRED_E2E_SCENARIO_PLATFORMS


def test_tracked_release_e2e_scaffold_check_rejects_stale_platforms(tmp_path):
    module = load_release_readiness_module()
    root = tmp_path
    docs = root / "docs"
    docs.mkdir()
    scaffold_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.json"
    scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))
    scaffold["scenarios"]["push_stt_complete"]["platforms"] = ["android"]
    (docs / "release-e2e-evidence.json").write_text(
        json.dumps(scaffold),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_tracked_release_e2e_scaffold(root, reporter)

    assert any(
        "scaffold scenario platforms are stale: push_stt_complete" in error
        for error in reporter.errors
    )


def test_tracked_release_e2e_scaffold_matches_strict_top_level_schema():
    scaffold_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.json"
    scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))

    assert set(scaffold) == {
        "tested_at",
        "tester",
        "backend_version",
        "client_version",
        "release_gate",
        "devices",
        "artifacts",
        "artifact_sha256",
        "scenarios",
    }
    assert scaffold["release_gate"] == {
        "android_release_signing": True,
        "ios_production_entitlements": True,
        "ios_entitlements_sha256": "0" * 64,
    }
    assert set(scaffold["artifact_sha256"]) == set(scaffold["artifacts"])


def test_tracked_release_e2e_scaffold_uses_release_android_artifact_path():
    scaffold_path = Path(__file__).resolve().parents[2] / "docs/release-e2e-evidence.json"
    scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))

    assert scaffold["artifacts"]["android_apk"].endswith("app-release.apk")


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


def test_tracked_secret_leak_check_accepts_current_product_files():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_tracked_secret_leaks(root, reporter)

    assert reporter.errors == []


def test_local_env_git_policy_accepts_current_repo_policy():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_local_env_git_policy(root, reporter)

    assert reporter.errors == []


def test_local_env_git_policy_rejects_tracked_env(monkeypatch, tmp_path):
    module = load_release_readiness_module()

    def fake_git_lines(root, args):
        if args[0] == "ls-files":
            return [".env"]
        if args[0] == "check-ignore":
            return [".gitignore:125:.env\t.env", ".gitignore:126:.env.*\t.env.local"]
        return []

    monkeypatch.setattr(module, "git_lines", fake_git_lines)

    reporter = module.Reporter()
    module.check_local_env_git_policy(tmp_path, reporter)

    assert any("Local secret env files are tracked: .env" in error for error in reporter.errors)


def test_local_env_git_policy_rejects_missing_ignore(monkeypatch, tmp_path):
    module = load_release_readiness_module()

    def fake_git_lines(root, args):
        if args[0] == "ls-files":
            return []
        if args[0] == "check-ignore":
            return [".gitignore:125:.env\t.env"]
        return []

    monkeypatch.setattr(module, "git_lines", fake_git_lines)

    reporter = module.Reporter()
    module.check_local_env_git_policy(tmp_path, reporter)

    assert any("Local secret env files are not ignored" in error for error in reporter.errors)


def test_tracked_secret_leak_check_rejects_real_api_key(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    (tmp_path / "README.md").write_text(
        "OPENAI_API_KEY=sk-proj-" + ("A" * 40),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "tracked_product_files", lambda root: [root / "README.md"])

    reporter = module.Reporter()
    module.check_tracked_secret_leaks(tmp_path, reporter)

    assert any("OpenAI API key" in error for error in reporter.errors)


def test_tracked_secret_leak_check_rejects_obsolete_api_key_secret(tmp_path, monkeypatch):
    module = load_release_readiness_module()
    (tmp_path / "README.md").write_text(
        "API_KEY_SECRET=your-secret-key",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "tracked_product_files", lambda root: [root / "README.md"])

    reporter = module.Reporter()
    module.check_tracked_secret_leaks(tmp_path, reporter)

    assert any("obsolete API_KEY_SECRET placeholder" in error for error in reporter.errors)


def test_production_compose_check_accepts_current_repo_policy():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_production_compose(root, reporter)

    assert reporter.errors == []


def test_production_compose_check_rejects_external_database_override(tmp_path):
    module = load_release_readiness_module()
    (tmp_path / "docker-compose.prod.yml").write_text(
        """
services:
      api:
        environment:
          - DATABASE_URL=${DATABASE_URL}
          - API_KEYS=${API_KEYS}
          - JWT_SECRET=${JWT_SECRET}
          - FIREBASE_CREDENTIALS_PATH=${FIREBASE_CREDENTIALS_PATH}
      worker:
        environment:
          - ENVIRONMENT=development
        """,
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_production_compose(tmp_path, reporter)

    assert any("required secrets are missing" in error for error in reporter.errors)
    assert any("ENVIRONMENT=production" in error for error in reporter.errors)
    assert any("internal async Postgres" in error for error in reporter.errors)
    assert any("external DATABASE_URL override" in error for error in reporter.errors)


def test_android_project_accepts_current_play_target_sdk():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_android_project(root, reporter)

    assert reporter.errors == []


def test_android_project_rejects_stale_play_target_sdk(tmp_path):
    module = load_release_readiness_module()
    write_minimal_android_project(tmp_path, target_sdk=34)

    reporter = module.Reporter()
    module.check_android_project(tmp_path, reporter)

    assert any("targetSdkVersion must be at least 35" in error for error in reporter.errors)


def test_ios_project_accepts_current_deployment_target():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_ios_project(root, reporter)

    assert reporter.errors == []


def test_ios_project_rejects_stale_deployment_target(tmp_path):
    module = load_release_readiness_module()
    write_minimal_ios_project(tmp_path, deployment_target="13.0")

    reporter = module.Reporter()
    module.check_ios_project(tmp_path, reporter)

    assert any("deployment target must be at least 15.0" in error for error in reporter.errors)


def test_ios_project_rejects_insecure_ats_exception(tmp_path):
    module = load_release_readiness_module()
    write_minimal_ios_project(tmp_path, insecure_ats_exception=True)

    reporter = module.Reporter()
    module.check_ios_project(tmp_path, reporter)

    assert any("ATS must not allow insecure HTTP loads" in error for error in reporter.errors)


def test_readme_release_status_accepts_release_candidate_language(tmp_path):
    module = load_release_readiness_module()
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "ANDROID_KEYSTORE_BASE64 ANDROID_KEYSTORE_PASSWORD ANDROID_KEY_ALIAS "
            "ANDROID_KEY_PASSWORD REQUIRE_ANDROID_RELEASE_SIGNING=true\n"
            "RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.json\n"
            "| **Android** | RC | `flutter build apk --release` 검증 완료 |"
        ),
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


def test_readme_release_status_rejects_stale_test_counts(tmp_path):
    module = load_release_readiness_module()
    (tmp_path / "README.md").write_text(
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "3655 백엔드 테스트\n"
            "| 백엔드 단위/통합/E2E | 3655개 | 100.00% |\n"
            "| 총합 | 3995개 | - |"
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert any("test counts must match" in error for error in reporter.errors)


def test_readme_release_status_rejects_android_debug_build_claim(tmp_path):
    module = load_release_readiness_module()
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "| **Android** | RC | `flutter build apk --debug` 검증 완료 |"
        ),
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert any("README Android RC status must reference release APK" in error for error in reporter.errors)


def test_readme_release_status_rejects_missing_android_signing_gate(tmp_path):
    module = load_release_readiness_module()
    (tmp_path / "README.md").write_text(
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "3995 백엔드 테스트 Flutter 415 4410개\n"
            "| 백엔드 단위/통합/E2E | 3995개 | 100.00% |\n"
            "| 총합 | 4410개 | - |\n"
            "| **Android** | RC | `flutter build apk --release` 검증 완료 |"
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert any("README strict gate must document Android release signing" in error for error in reporter.errors)


def test_readme_release_status_rejects_example_evidence_as_strict_input(tmp_path):
    module = load_release_readiness_module()
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "ANDROID_KEYSTORE_BASE64 ANDROID_KEYSTORE_PASSWORD ANDROID_KEY_ALIAS "
            "ANDROID_KEY_PASSWORD REQUIRE_ANDROID_RELEASE_SIGNING=true\n"
            "RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.example.json\n"
            "| **Android** | RC | `flutter build apk --release` 검증 완료 |"
        ),
    )

    reporter = module.Reporter()
    module.check_readme_release_status(tmp_path, reporter)

    assert any("must not use example release E2E evidence" in error for error in reporter.errors)


def test_owll_benchmark_doc_accepts_current_competitor_evidence():
    module = load_release_readiness_module()
    root = Path(__file__).resolve().parents[2]

    reporter = module.Reporter()
    module.check_owll_benchmark_doc(root, reporter)

    assert reporter.errors == []


def test_owll_benchmark_doc_rejects_stale_competitor_evidence(tmp_path):
    module = load_release_readiness_module()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/owll-benchmark-prd.md").write_text(
        "Owll benchmark without current store evidence.",
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_owll_benchmark_doc(tmp_path, reporter)

    assert any("Owll benchmark PRD captures current competitor evidence" in error for error in reporter.errors)


def test_release_procedure_rejects_version_drift(tmp_path):
    module = load_release_readiness_module()
    repo_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repo_root / "docs", tmp_path / "docs")
    write_tone_policy_files(tmp_path)
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "**버전**: 1.7.0\n"
            "✅ SPEC-ONE\n"
            "✅ SPEC-TWO\n"
        ),
    )
    (tmp_path / "docs/release-procedure.md").write_text(
        (
            "client/scripts/create_release_e2e_evidence.py\n"
            "17개 required scenario\n"
            "`platforms`\n"
            '["android", "ios"]\n'
            '["android"]\n'
            '["ios"]\n'
            "python3 client/scripts/verify_mobile_release_runner.py\n"
            "python3 client/scripts/verify_github_mobile_release_env.py\n"
            "REQUIRE_ANDROID_RELEASE_SIGNING=true\n"
            "IOS_RELEASE_ENTITLEMENTS_PATH\n"
            "ios-release-entitlements.plist\n"
            "aps-environment\n"
            "get-task-allow\n"
            "python3 client/scripts/verify_release_readiness.py --strict\n"
            "2개 SPEC 전부 완료\n"
            "2 SPECs completed\n"
            "3995 passed\n"
            "Flutter: 415 passed\n"
            "`verify_mobile_release_runner.py` PASS\n"
            "`verify_github_mobile_release_env.py` PASS\n"
            "Production Ready v1.6.0\n"
            "git tag v1.6.0\n"
            "gh release create v1.6.0\n"
            "--title \"v1.6.0 — Production Ready\"\n"
        ),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_docs(tmp_path, reporter)

    assert any("version must match README" in error for error in reporter.errors)


def test_release_procedure_rejects_missing_platform_contract(tmp_path):
    module = load_release_readiness_module()
    repo_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repo_root / "docs", tmp_path / "docs")
    write_tone_policy_files(tmp_path)
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "**버전**: 1.7.0\n"
            "✅ SPEC-ONE\n"
            "✅ SPEC-TWO\n"
        ),
    )
    procedure = (tmp_path / "docs/release-procedure.md").read_text(encoding="utf-8")
    (tmp_path / "docs/release-procedure.md").write_text(
        procedure.replace("`platforms`", "`platform_list`"),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_docs(tmp_path, reporter)

    assert any(
        "Release procedure matches current strict E2E evidence workflow" in error
        and "`platforms`" in error
        for error in reporter.errors
    )


def test_release_docs_reject_missing_strict_android_signing_env(tmp_path):
    module = load_release_readiness_module()
    repo_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repo_root / "docs", tmp_path / "docs")
    write_tone_policy_files(tmp_path)
    write_readme_status(
        tmp_path,
        (
            "Release Candidate strict 실기기 release evidence 대기 RELEASE_E2E_EVIDENCE_PATH\n"
            "**버전**: 1.7.0\n"
            "✅ SPEC-ONE\n"
            "✅ SPEC-TWO\n"
        ),
    )
    checklist = (tmp_path / "docs/e2e-device-checklist.md").read_text(encoding="utf-8")
    procedure = (tmp_path / "docs/release-procedure.md").read_text(encoding="utf-8")
    (tmp_path / "docs/e2e-device-checklist.md").write_text(
        checklist.replace("REQUIRE_ANDROID_RELEASE_SIGNING", "ANDROID_SIGNING_MODE"),
        encoding="utf-8",
    )
    (tmp_path / "docs/release-procedure.md").write_text(
        procedure.replace("REQUIRE_ANDROID_RELEASE_SIGNING=true", "ANDROID_SIGNING_MODE=true"),
        encoding="utf-8",
    )

    reporter = module.Reporter()
    module.check_docs(tmp_path, reporter)

    assert any("E2E checklist missing REQUIRE_ANDROID_RELEASE_SIGNING" in error for error in reporter.errors)
    assert any(
        "Release procedure matches current strict E2E evidence workflow" in error
        and "REQUIRE_ANDROID_RELEASE_SIGNING=true" in error
        for error in reporter.errors
    )


def test_mobile_workflow_exposes_manual_strict_release_gate():
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/mobile.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    required_snippets = [
        "workflow_dispatch:",
        "evidence_path:",
        "README.md",
        "pyproject.toml",
        ".gitignore",
        "docs/release-procedure.md",
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
        "python3 client/scripts/verify_mobile_release_runner.py",
        "Verify strict release input paths",
        'test "$RELEASE_E2E_EVIDENCE_PATH" != "docs/release-e2e-evidence.example.json"',
        'test -f "$RELEASE_E2E_EVIDENCE_PATH"',
        'test -f "$IOS_RELEASE_ENTITLEMENTS_PATH"',
        "./scripts/verify_mobile.sh --native",
        "python3 client/scripts/verify_release_readiness.py --strict",
        "docs/release-e2e-evidence.json",
        "backend/tests/test_configure_github_mobile_release_env.py",
        "backend/tests/test_create_release_e2e_evidence.py",
        "backend/tests/test_github_mobile_release_env.py",
        "backend/tests/test_mobile_release_runner.py",
        "backend/tests/test_release_readiness_evidence.py",
    ]

    for snippet in required_snippets:
        assert snippet in workflow
