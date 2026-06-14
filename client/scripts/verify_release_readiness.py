#!/usr/bin/env python3
"""Validate mobile release readiness before external E2E testing.

Default mode checks repository-local release wiring that should always be true.
Use --strict on a secured machine/CI job with Firebase, APNs, App Store Connect,
and physical-device secrets available.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ID = "voice-to-textnote"
ANDROID_PACKAGE = "com.voicetextnote.app"
IOS_BUNDLE_ID = "com.voicetextnote.app"
URL_SCHEME = "voicetextnote"


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def ok(self, message: str) -> None:
        print(f"PASS {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"WARN {message}")

    def fail(self, message: str) -> None:
        self.errors.append(message)
        print(f"FAIL {message}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require_file(reporter: Reporter, path: Path, label: str) -> bool:
    if path.is_file():
        reporter.ok(f"{label}: {path}")
        return True
    reporter.fail(f"{label} missing: {path}")
    return False


def check_android_firebase(root: Path, reporter: Reporter) -> None:
    path = root / "client/android/app/google-services.json"
    if not require_file(reporter, path, "Android Firebase config"):
        return
    data = json.loads(read_text(path))
    project_info = data.get("project_info", {})
    clients = data.get("client", [])

    if project_info.get("project_id") == PROJECT_ID:
        reporter.ok(f"Android Firebase project_id is {PROJECT_ID}")
    else:
        reporter.fail(f"Android Firebase project_id is not {PROJECT_ID}")

    package_names = {
        client.get("client_info", {})
        .get("android_client_info", {})
        .get("package_name")
        for client in clients
    }
    if ANDROID_PACKAGE in package_names:
        reporter.ok(f"Android Firebase package is {ANDROID_PACKAGE}")
    else:
        reporter.fail(f"Android Firebase package {ANDROID_PACKAGE} not found")

    api_keys = [
        key.get("current_key")
        for client in clients
        for key in client.get("api_key", [])
        if key.get("current_key")
    ]
    if api_keys:
        reporter.ok("Android Firebase API key is present")
    else:
        reporter.fail("Android Firebase API key is missing")


def check_ios_firebase(root: Path, reporter: Reporter) -> None:
    path = root / "client/ios/Runner/GoogleService-Info.plist"
    if not require_file(reporter, path, "iOS Firebase config"):
        return
    data = plistlib.loads(path.read_bytes())
    expected = {
        "PROJECT_ID": PROJECT_ID,
        "BUNDLE_ID": IOS_BUNDLE_ID,
    }
    for key, value in expected.items():
        if data.get(key) == value:
            reporter.ok(f"iOS Firebase {key} is {value}")
        else:
            reporter.fail(f"iOS Firebase {key} is not {value}")
    if data.get("GOOGLE_APP_ID") and data.get("API_KEY"):
        reporter.ok("iOS Firebase app id and API key are present")
    else:
        reporter.fail("iOS Firebase app id or API key missing")


def check_flutter_options(root: Path, reporter: Reporter) -> None:
    path = root / "client/lib/firebase_options.dart"
    if not require_file(reporter, path, "FlutterFire options"):
        return
    content = read_text(path)
    expected_snippets = [
        f"projectId: '{PROJECT_ID}'",
        f"iosBundleId: '{IOS_BUNDLE_ID}'",
        "TargetPlatform.android",
        "TargetPlatform.iOS",
    ]
    for snippet in expected_snippets:
        if snippet in content:
            reporter.ok(f"FlutterFire options contain {snippet}")
        else:
            reporter.fail(f"FlutterFire options missing {snippet}")


def check_ios_project(root: Path, reporter: Reporter) -> None:
    info_path = root / "client/ios/Runner/Info.plist"
    entitlements_path = root / "client/ios/Runner/Runner.entitlements"
    xcodeproj_path = root / "client/ios/Runner.xcodeproj/project.pbxproj"
    app_delegate_path = root / "client/ios/Runner/AppDelegate.swift"
    for path, label in [
        (info_path, "iOS Info.plist"),
        (entitlements_path, "iOS entitlements"),
        (xcodeproj_path, "iOS Xcode project"),
        (app_delegate_path, "iOS AppDelegate"),
    ]:
        if not require_file(reporter, path, label):
            return

    info = plistlib.loads(info_path.read_bytes())
    background_modes = set(info.get("UIBackgroundModes", []))
    if {"audio", "remote-notification"}.issubset(background_modes):
        reporter.ok("iOS background modes include audio and remote-notification")
    else:
        reporter.fail("iOS background modes missing audio or remote-notification")

    url_types = info.get("CFBundleURLTypes", [])
    schemes = {
        scheme
        for url_type in url_types
        for scheme in url_type.get("CFBundleURLSchemes", [])
    }
    if URL_SCHEME in schemes:
        reporter.ok(f"iOS URL scheme is {URL_SCHEME}")
    else:
        reporter.fail(f"iOS URL scheme {URL_SCHEME} missing")

    entitlements = plistlib.loads(entitlements_path.read_bytes())
    aps_environment = entitlements.get("aps-environment")
    if aps_environment in {"development", "production"}:
        reporter.ok(f"iOS APNs entitlement is {aps_environment}")
        if aps_environment != "production":
            reporter.warn("App Store distribution still requires production APNs entitlement from signing profile")
    else:
        reporter.fail("iOS aps-environment entitlement missing")

    project = read_text(xcodeproj_path)
    if f"PRODUCT_BUNDLE_IDENTIFIER = {IOS_BUNDLE_ID};" in project:
        reporter.ok(f"iOS bundle id is {IOS_BUNDLE_ID}")
    else:
        reporter.fail(f"iOS bundle id {IOS_BUNDLE_ID} missing from project")
    if re.search(r"DEVELOPMENT_TEAM = [A-Z0-9]{10};", project):
        reporter.ok("iOS development team is configured in Xcode project")
    else:
        reporter.warn("iOS development team is not configured in Xcode project")

    app_delegate = read_text(app_delegate_path)
    recording_contract = [
        'FlutterMethodChannel(\n      name: channelName',
        'private let channelName = "com.voicetextnote.app/recording"',
        'method == "startBackgroundTask"',
        'method == "stopBackgroundTask"',
        'method == "flushRecording"',
        "UIApplication.shared.beginBackgroundTask",
        "UIApplication.shared.endBackgroundTask",
        "AVAudioSession.interruptionNotification",
        "AVAudioSession.routeChangeNotification",
        'method: "onInterruptionBegin"',
        'method: "onInterruptionEnd"',
        'method: "onRouteChange"',
    ]
    missing_recording_contract = [
        snippet for snippet in recording_contract if snippet not in app_delegate
    ]
    if not missing_recording_contract:
        reporter.ok("iOS AppDelegate implements recording MethodChannel and AVAudioSession observers")
    else:
        reporter.fail(
            "iOS AppDelegate recording contract missing: "
            + ", ".join(missing_recording_contract)
        )


def check_android_project(root: Path, reporter: Reporter) -> None:
    gradle_path = root / "client/android/app/build.gradle"
    manifest_path = root / "client/android/app/src/main/AndroidManifest.xml"
    network_path = root / "client/android/app/src/main/res/xml/network_security_config.xml"
    debug_network_path = root / "client/android/app/src/debug/res/xml/network_security_config.xml"
    for path, label in [
        (gradle_path, "Android app Gradle file"),
        (manifest_path, "Android manifest"),
        (network_path, "Android release/profile network security config"),
        (debug_network_path, "Android debug network security config"),
    ]:
        if not require_file(reporter, path, label):
            return
    gradle = read_text(gradle_path)
    if f'applicationId "{ANDROID_PACKAGE}"' in gradle and f"namespace '{ANDROID_PACKAGE}'" in gradle:
        reporter.ok(f"Android package/application id is {ANDROID_PACKAGE}")
    else:
        reporter.fail(f"Android package/application id {ANDROID_PACKAGE} missing")

    manifest = read_text(manifest_path)
    if 'android:networkSecurityConfig="@xml/network_security_config"' in manifest:
        reporter.ok("Android manifest references network security config")
    else:
        reporter.fail("Android manifest does not reference network security config")

    release_network = read_text(network_path)
    if '<base-config cleartextTrafficPermitted="false">' in release_network:
        reporter.ok("Android release/profile cleartext traffic denied by default")
    else:
        reporter.fail("Android release/profile base cleartext denial missing")
    if (
        '<domain-config cleartextTrafficPermitted="true">' not in release_network
        and "<domain " not in release_network
    ):
        reporter.ok("Android release/profile config has no cleartext domain exceptions")
    else:
        reporter.fail("Android release/profile config must not allow cleartext domain exceptions")

    debug_network = read_text(debug_network_path)
    if '<base-config cleartextTrafficPermitted="false">' in debug_network:
        reporter.ok("Android debug cleartext traffic denied by default outside exceptions")
    else:
        reporter.fail("Android debug base cleartext denial missing")
    debug_cleartext_hosts = set(
        re.findall(r"<domain\b[^>]*>([^<]+)</domain>", debug_network)
    )
    expected_debug_hosts = {"localhost", "100.110.255.105"}
    if debug_cleartext_hosts == expected_debug_hosts:
        reporter.ok("Android debug cleartext exceptions are limited to local/staging hosts")
    else:
        reporter.fail("Android debug cleartext exceptions missing local/staging hosts")


def check_backend_push(root: Path, reporter: Reporter) -> None:
    config_path = root / "backend/app/config.py"
    service_path = root / "backend/services/push_service.py"
    hook_path = root / "backend/app/workers/hooks/celery_push_hooks.py"
    device_model_path = root / "backend/db/device_token_models.py"
    device_api_path = root / "backend/app/api/v1/auth/devices.py"
    device_migration_path = root / "alembic/versions/003_add_device_id_to_device_tokens.py"
    for path, label in [
        (config_path, "Backend config"),
        (service_path, "Backend push service"),
        (hook_path, "Celery push hooks"),
        (device_model_path, "Device token model"),
        (device_api_path, "Device registration API"),
        (device_migration_path, "Device token device_id migration"),
    ]:
        if not require_file(reporter, path, label):
            return
    if "firebase_credentials_path" in read_text(config_path):
        reporter.ok("Backend exposes firebase_credentials_path setting")
    else:
        reporter.fail("Backend firebase_credentials_path setting missing")
    service = read_text(service_path)
    if "firebase_admin" in service and "messaging" in service:
        reporter.ok("Backend push service imports Firebase Admin messaging")
    else:
        reporter.fail("Backend push service Firebase Admin wiring missing")
    hooks = read_text(hook_path)
    if "on_pipeline_success" in hooks and "on_pipeline_failure" in hooks:
        reporter.ok("Celery success/failure push hooks are present")
    else:
        reporter.fail("Celery push hooks missing success/failure handlers")
    device_model = read_text(device_model_path)
    device_api = read_text(device_api_path)
    device_migration = read_text(device_migration_path)
    if "device_id" in device_model and "ix_device_tokens_user_device_id" in device_migration:
        reporter.ok("Device tokens persist device_id with user/device lookup migration")
    else:
        reporter.fail("Device token device_id persistence or migration missing")
    if "user_id=str(current_user.id)" in device_api and "device_id=device_id" in device_api:
        reporter.ok("Device unregister uses requested user_id/device_id mapping")
    else:
        reporter.fail("Device unregister does not use requested user_id/device_id mapping")


def check_docs(root: Path, reporter: Reporter) -> None:
    required = [
        (root / "docs/firebase-setup-guide.md", "Firebase setup guide"),
        (root / "docs/e2e-device-checklist.md", "Device E2E checklist"),
        (root / "docs/app-store-metadata.md", "App Store metadata"),
    ]
    for path, label in required:
        if not require_file(reporter, path, label):
            return
    firebase_doc = read_text(root / "docs/firebase-setup-guide.md")
    for snippet in ["FIREBASE_CREDENTIALS_PATH", "APNs", "google-services.json", "GoogleService-Info.plist"]:
        if snippet in firebase_doc:
            reporter.ok(f"Firebase guide documents {snippet}")
        else:
            reporter.fail(f"Firebase guide missing {snippet}")
    e2e_doc = read_text(root / "docs/e2e-device-checklist.md")
    e2e_requirements = [
        ("Push/푸시 알림", ("Push", "푸시 알림")),
        ("백그라운드 녹음", ("백그라운드 녹음",)),
        ("./scripts/verify_mobile.sh --native", ("./scripts/verify_mobile.sh --native",)),
    ]
    for label, snippets in e2e_requirements:
        if any(snippet in e2e_doc for snippet in snippets):
            reporter.ok(f"E2E checklist covers {label}")
        else:
            reporter.fail(f"E2E checklist missing {label}")
    app_store_doc = read_text(root / "docs/app-store-metadata.md")
    for snippet in ["App Store Connect", "Privacy Policy", "com.voicetextnote.app"]:
        if snippet in app_store_doc:
            reporter.ok(f"App Store metadata covers {snippet}")
        else:
            reporter.fail(f"App Store metadata missing {snippet}")


def check_release_doc_placeholders(root: Path, reporter: Reporter) -> None:
    placeholder_patterns = (
        r"\[To be updated",
        r"\[App Store 제출 시 업데이트 예정\]",
        r"\bTBD\b",
        r"\bTODO\b",
    )
    for relative_path in [
        "docs/app-store-metadata.md",
        "docs/privacy-policy.md",
        "docs/e2e-device-checklist.md",
    ]:
        path = root / relative_path
        content = read_text(path)
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in placeholder_patterns):
            reporter.fail(f"Release documentation contains unresolved placeholder: {relative_path}")
        else:
            reporter.ok(f"Release documentation has no unresolved placeholders: {relative_path}")


def check_service_account(path: Path, reporter: Reporter) -> None:
    if not path.is_file():
        reporter.fail(f"FIREBASE_CREDENTIALS_PATH does not point to a file: {path}")
        return
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        reporter.fail(f"Firebase service account JSON is invalid: {exc}")
        return
    expected = {
        "type": "service_account",
        "project_id": PROJECT_ID,
    }
    for key, value in expected.items():
        if data.get(key) == value:
            reporter.ok(f"Firebase service account {key} is valid")
        else:
            reporter.fail(f"Firebase service account {key} is not {value}")
    private_key = data.get("private_key", "")
    client_email = data.get("client_email", "")
    if "BEGIN PRIVATE KEY" in private_key:
        reporter.ok("Firebase service account private key is present")
    else:
        reporter.fail("Firebase service account private key missing")
    if client_email.endswith(".gserviceaccount.com"):
        reporter.ok("Firebase service account client_email is present")
    else:
        reporter.fail("Firebase service account client_email missing or invalid")


def require_env_file(reporter: Reporter, env_name: str, label: str, suffix: str | None = None) -> None:
    value = os.environ.get(env_name, "")
    if not value:
        reporter.fail(f"{label}: {env_name} is not set")
        return
    path = Path(value).expanduser()
    if suffix and path.suffix != suffix:
        reporter.fail(f"{label}: {env_name} must point to a {suffix} file")
        return
    if path.is_file():
        reporter.ok(f"{label}: {env_name} file exists")
    else:
        reporter.fail(f"{label}: {env_name} file missing at {path}")


def require_env_value(reporter: Reporter, env_name: str, label: str, pattern: str | None = None) -> None:
    value = os.environ.get(env_name, "")
    if not value:
        reporter.fail(f"{label}: {env_name} is not set")
        return
    if pattern and not re.fullmatch(pattern, value):
        reporter.fail(f"{label}: {env_name} does not match expected format")
        return
    reporter.ok(f"{label}: {env_name} is set")


def read_command_output(command: list[str]) -> tuple[int, str]:
    if shutil.which(command[0]) is None:
        return 127, ""
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode, completed.stdout


def require_android_device(reporter: Reporter) -> None:
    serial = os.environ.get("ANDROID_DEVICE_SERIAL", "")
    require_env_value(reporter, "ANDROID_DEVICE_SERIAL", "Android physical test device serial")
    if not serial:
        return

    code, output = read_command_output(["adb", "devices", "-l"])
    if code != 0:
        reporter.fail("Android physical test device serial: adb devices failed or adb is unavailable")
        return
    connected_serials = {
        line.split()[0]
        for line in output.splitlines()
        if line.strip() and "\tdevice" in line
    }
    if serial in connected_serials:
        reporter.ok("Android physical test device serial is connected via adb")
    else:
        reporter.fail(f"Android physical test device serial {serial} is not connected via adb")


def require_ios_device(reporter: Reporter) -> None:
    udid = os.environ.get("IOS_DEVICE_UDID", "")
    require_env_value(reporter, "IOS_DEVICE_UDID", "iOS physical test device UDID")
    if not udid:
        return

    code, output = read_command_output(["xcrun", "devicectl", "list", "devices"])
    if code != 0:
        reporter.fail("iOS physical test device UDID: xcrun devicectl failed or Xcode tools are unavailable")
        return
    matching_lines = [line for line in output.splitlines() if udid in line]
    if matching_lines and any(re.search(r"\savailable\s", line) for line in matching_lines):
        reporter.ok("iOS physical test device UDID is connected and available")
    elif matching_lines:
        reporter.fail(f"iOS physical test device UDID {udid} is known but not available")
    else:
        reporter.fail(f"iOS physical test device UDID {udid} is not visible to xcrun devicectl")


def check_strict_external(reporter: Reporter) -> None:
    credentials = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    if credentials:
        check_service_account(Path(credentials).expanduser(), reporter)
    else:
        reporter.fail("Firebase service account: FIREBASE_CREDENTIALS_PATH is not set")

    require_env_file(reporter, "APNS_AUTH_KEY_PATH", "APNs auth key", ".p8")
    require_env_value(reporter, "APNS_KEY_ID", "APNs key id", r"[A-Z0-9]{10}")
    require_env_value(reporter, "APNS_TEAM_ID", "APNs team id", r"[A-Z0-9]{10}")

    require_env_file(reporter, "APP_STORE_CONNECT_API_KEY_PATH", "App Store Connect API key", ".p8")
    require_env_value(reporter, "APP_STORE_CONNECT_KEY_ID", "App Store Connect key id", r"[A-Z0-9]{10}")
    require_env_value(reporter, "APP_STORE_CONNECT_ISSUER_ID", "App Store Connect issuer id")

    require_android_device(reporter)
    require_ios_device(reporter)
    require_env_value(reporter, "FIREBASE_TEST_DEVICE_TOKEN", "Firebase test device token")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require Firebase service account, APNs, App Store Connect, and device-test secrets.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    reporter = Reporter()

    check_android_firebase(root, reporter)
    check_ios_firebase(root, reporter)
    check_flutter_options(root, reporter)
    check_ios_project(root, reporter)
    check_android_project(root, reporter)
    check_backend_push(root, reporter)
    check_docs(root, reporter)

    if args.strict:
        check_release_doc_placeholders(root, reporter)
        check_strict_external(reporter)
    else:
        reporter.warn("Strict external checks skipped; run with --strict when release secrets/devices are available")

    print(
        f"release_readiness: {len(reporter.errors)} errors, "
        f"{len(reporter.warnings)} warnings"
    )
    return 1 if reporter.errors else 0


if __name__ == "__main__":
    sys.exit(main())
