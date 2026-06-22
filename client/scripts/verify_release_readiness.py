#!/usr/bin/env python3
"""Validate mobile release readiness before external E2E testing.

Default mode checks repository-local release wiring that should always be true.
Use --strict on a secured machine/CI job with Firebase, APNs, App Store Connect,
and physical-device secrets available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ID = "voice-to-textnote"
ANDROID_PACKAGE = "com.voicetextnote.app"
IOS_BUNDLE_ID = "com.voicetextnote.app"
URL_SCHEME = "voicetextnote"
MIN_IOS_DEPLOYMENT_TARGET = (15, 0)
MIN_GOOGLE_PLAY_TARGET_SDK = 35
REQUIRED_E2E_SCENARIOS = {
    "permission_microphone_initial": "Initial microphone permission prompt",
    "permission_denied_recovery": "Permission denial recovery UI",
    "ios_background_recording_lock": "iOS background recording while locked",
    "ios_interruption_resume": "iOS call interruption resume",
    "ios_bluetooth_route_change": "iOS Bluetooth route change",
    "unfinished_recording_recovery": "Unfinished recording recovery after restart",
    "push_stt_complete": "Push received for STT completion",
    "push_summary_complete": "Push received for summary completion",
    "push_failure": "Push received for processing failure",
    "push_deeplink_background": "Push deeplink while app is backgrounded",
    "push_deeplink_cold_start": "Push deeplink from cold start",
    "android_foreground_service": "Android foreground recording notification",
    "android_debug_tailscale_cleartext_allowed": "Android debug Tailscale HTTP allowed",
    "android_release_cleartext_blocked": "Android release HTTP blocked",
    "ios_release_http_blocked": "iOS release HTTP blocked",
    "export_share_android": "Android PDF share sheet",
    "export_share_ios": "iOS PDF share sheet",
}
REQUIRED_E2E_SCENARIO_PLATFORMS = {
    "permission_microphone_initial": ("android", "ios"),
    "permission_denied_recovery": ("android", "ios"),
    "ios_background_recording_lock": ("ios",),
    "ios_interruption_resume": ("ios",),
    "ios_bluetooth_route_change": ("ios",),
    "unfinished_recording_recovery": ("android", "ios"),
    "push_stt_complete": ("android", "ios"),
    "push_summary_complete": ("android", "ios"),
    "push_failure": ("android", "ios"),
    "push_deeplink_background": ("android", "ios"),
    "push_deeplink_cold_start": ("android", "ios"),
    "android_foreground_service": ("android",),
    "android_debug_tailscale_cleartext_allowed": ("android",),
    "android_release_cleartext_blocked": ("android",),
    "ios_release_http_blocked": ("ios",),
    "export_share_android": ("android",),
    "export_share_ios": ("ios",),
}
CANONICAL_RELEASE_ARTIFACT_PATHS = {
    "android_apk": "client/build/app/outputs/flutter-apk/app-release.apk",
    "ios_runner_app": "client/build/ios/iphoneos/Runner.app",
}
EXPECTED_STRICT_MISSING_INPUT_ERRORS = 13
CURRENT_BACKEND_TEST_COUNT = 3998
CURRENT_FLUTTER_TEST_COUNT = 415
CURRENT_TOTAL_TEST_COUNT = CURRENT_BACKEND_TEST_COUNT + CURRENT_FLUTTER_TEST_COUNT
APP_STORE_CONNECT_ISSUER_ID_PATTERN = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
UNRESOLVED_EVIDENCE_PATTERNS = (
    r"\bTODO\b",
    r"\bTBD\b",
    r"to be configured",
    r"pending manual",
    r"requires manual",
    r"not yet configured",
)
RELEASE_E2E_OBSERVATION_ARTIFACT_PATTERNS = (
    r"\bscreenshots?\b",
    r"\bscreen\s*recording\b",
    r"\bvideos?\b",
    r"\blogs?\b",
    r"\btraces?\b",
    r"\battachments?\b",
    r"스크린샷",
    r"화면\s*녹화",
    r"동영상",
    r"로그",
    r"첨부",
)
RELEASE_E2E_OBSERVATION_REFERENCE_PATTERNS = (
    r"https?://\S+",
    r"\b[\w./-]+\.(?:heic|jpeg|jpg|log|mov|mp4|png|trace|txt|zip)\b",
    r"\bartifact:[A-Za-z0-9._/-]+\b",
    r"\battachment:[A-Za-z0-9._/-]+\b",
)
MIN_RELEASE_E2E_EVIDENCE_CHARS = 24
MAX_RELEASE_E2E_EVIDENCE_AGE = timedelta(days=14)
APK_SIGNATURE_BLOCK_MAGIC = b"APK Sig Block 42"
SECRET_SCAN_PATHS = (
    ".github/workflows",
    "README.md",
    "backend",
    "client",
    "docs",
    "pyproject.toml",
)
SECRET_SCAN_EXCLUDED_PATHS = {
    "docs/release-e2e-evidence.json",
    "docs/release-e2e-evidence.example.json",
}
SECRET_SCAN_EXCLUDED_PREFIXES = (
    "backend/tests/",
    "client/test/",
)
TRACKED_SECRET_PATTERNS = (
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b")),
    ("obsolete API_KEY_SECRET placeholder", re.compile(r"API_KEY_SECRET\s*=\s*your-secret-key")),
)
LOCAL_SECRET_ENV_FILES = (".env", ".env.local", ".env.production")


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


def git_lines(root: Path, args: list[str]) -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line for line in output.splitlines() if line]


def tracked_product_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in git_lines(root, ["ls-files", *SECRET_SCAN_PATHS]):
        if not relative or relative in SECRET_SCAN_EXCLUDED_PATHS:
            continue
        if any(relative.startswith(prefix) for prefix in SECRET_SCAN_EXCLUDED_PREFIXES):
            continue
        path = root / relative
        if path.is_file():
            paths.append(path)
    return paths


def check_local_env_git_policy(root: Path, reporter: Reporter) -> None:
    tracked_env_files = set(git_lines(root, ["ls-files", *LOCAL_SECRET_ENV_FILES]))
    forbidden_tracked = sorted(name for name in LOCAL_SECRET_ENV_FILES if name in tracked_env_files)
    if forbidden_tracked:
        reporter.fail("Local secret env files are tracked: " + ", ".join(forbidden_tracked))
    else:
        reporter.ok("Local secret env files are not tracked")

    ignored_files = set()
    for line in git_lines(root, ["check-ignore", "-v", *LOCAL_SECRET_ENV_FILES]):
        ignored_files.add(line.rsplit(maxsplit=1)[-1])
    missing_ignore = sorted(name for name in LOCAL_SECRET_ENV_FILES if name not in ignored_files)
    if missing_ignore:
        reporter.fail("Local secret env files are not ignored: " + ", ".join(missing_ignore))
    else:
        reporter.ok("Local secret env files are ignored by git")


def check_tracked_secret_leaks(root: Path, reporter: Reporter) -> None:
    leaks: list[str] = []
    for path in tracked_product_files(root):
        try:
            content = read_text(path)
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(root)
        for label, pattern in TRACKED_SECRET_PATTERNS:
            if pattern.search(content):
                leaks.append(f"{relative}: {label}")

    if leaks:
        for leak in leaks:
            reporter.fail(f"Tracked secret placeholder or credential detected: {leak}")
    else:
        reporter.ok("Tracked product files contain no release-blocking secret placeholders")


def check_production_compose(root: Path, reporter: Reporter) -> None:
    path = root / "docker-compose.prod.yml"
    if not require_file(reporter, path, "Production Docker Compose"):
        return
    content = read_text(path)
    required_snippets = [
        "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}",
        "${REDIS_PASSWORD:?REDIS_PASSWORD is required}",
        "${API_KEYS:?API_KEYS is required}",
        "${JWT_SECRET:?JWT_SECRET is required}",
        "${OPENAI_API_KEY:?OPENAI_API_KEY is required}",
        "${FIREBASE_CREDENTIALS_PATH:?FIREBASE_CREDENTIALS_PATH is required}",
        "FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase-service-account.json",
        "/run/secrets/firebase-service-account.json:ro",
    ]
    require_snippets(
        reporter,
        content,
        required_snippets,
        "Production compose fails fast when required secrets are missing",
    )

    if content.count("ENVIRONMENT=production") >= 2:
        reporter.ok("Production compose forces backend services into production environment")
    else:
        reporter.fail("Production compose must force api and worker ENVIRONMENT=production")

    internal_database_url = (
        "postgresql+asyncpg://${POSTGRES_USER:-voicenote}:"
        "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@postgres:5432/"
        "${POSTGRES_DB:-voicenote}"
    )
    if content.count(internal_database_url) >= 2:
        reporter.ok("Production compose forces api and worker to internal async Postgres")
    else:
        reporter.fail("Production compose must force api and worker to internal async Postgres")

    if "DATABASE_URL=${DATABASE_URL}" in content:
        reporter.fail("Production compose must not accept external DATABASE_URL override")
    else:
        reporter.ok("Production compose does not accept external DATABASE_URL override")


def require_file(reporter: Reporter, path: Path, label: str) -> bool:
    if path.is_file():
        reporter.ok(f"{label}: {path}")
        return True
    reporter.fail(f"{label} missing: {path}")
    return False


def read_png_size_and_color_type(path: Path) -> tuple[int, int, int] | None:
    """Return PNG width, height, and color type without external dependencies."""
    data = path.read_bytes()
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    chunk_type = data[12:16]
    if chunk_type != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    return width, height, color_type


def check_png_icon(
    reporter: Reporter,
    path: Path,
    label: str,
    expected_size: tuple[int, int],
    allow_alpha: bool,
) -> None:
    if not require_file(reporter, path, label):
        return
    png = read_png_size_and_color_type(path)
    if png is None:
        reporter.fail(f"{label} is not a valid PNG")
        return
    width, height, color_type = png
    if (width, height) == expected_size:
        reporter.ok(f"{label} size is {width}x{height}")
    else:
        reporter.fail(
            f"{label} size is {width}x{height}, expected {expected_size[0]}x{expected_size[1]}"
        )
    has_alpha = color_type in {4, 6}
    if allow_alpha or not has_alpha:
        reporter.ok(f"{label} alpha channel policy is valid")
    else:
        reporter.fail(f"{label} must not include an alpha channel")


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
        client.get("client_info", {}).get("android_client_info", {}).get("package_name")
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


def require_snippets(
    reporter: Reporter,
    content: str,
    snippets: list[str],
    label: str,
) -> bool:
    missing = [snippet for snippet in snippets if snippet not in content]
    if not missing:
        reporter.ok(label)
        return True
    reporter.fail(f"{label} missing: " + ", ".join(missing))
    return False


def check_local_stt(root: Path, reporter: Reporter) -> None:
    pubspec_path = root / "client/pubspec.yaml"
    lock_path = root / "client/pubspec.lock"
    runtime_path = root / "client/lib/services/local_stt_runtime_whisper.dart"
    service_path = root / "client/lib/services/local_stt_service.dart"
    provider_path = root / "client/lib/services/local_stt_provider.dart"
    smoke_path = root / "client/tool/local_stt_smoke.dart"
    ios_pod_lock_path = root / "client/ios/Podfile.lock"
    macos_pod_lock_path = root / "client/macos/Podfile.lock"
    for path, label in [
        (pubspec_path, "Flutter pubspec"),
        (lock_path, "Flutter pubspec lock"),
        (runtime_path, "Whisper runtime adapter"),
        (service_path, "Local STT service"),
        (provider_path, "Local STT provider"),
        (smoke_path, "Local STT smoke runner"),
        (ios_pod_lock_path, "iOS Podfile.lock"),
        (macos_pod_lock_path, "macOS Podfile.lock"),
    ]:
        if not require_file(reporter, path, label):
            return

    pubspec = read_text(pubspec_path)
    lock = read_text(lock_path)
    runtime = read_text(runtime_path)
    service = read_text(service_path)
    provider = read_text(provider_path)
    smoke = read_text(smoke_path)
    ios_pod_lock = read_text(ios_pod_lock_path)
    macos_pod_lock = read_text(macos_pod_lock_path)

    require_snippets(
        reporter,
        pubspec,
        ["whisper_ggml_plus: ^1.5.2"],
        "Flutter pubspec pins whisper_ggml_plus dependency",
    )
    require_snippets(
        reporter,
        lock,
        ["name: whisper_ggml_plus", 'version: "1.5.2"'],
        "Flutter pubspec.lock resolves whisper_ggml_plus 1.5.2",
    )
    require_snippets(
        reporter,
        runtime,
        [
            "package:whisper_ggml_plus/whisper_ggml_plus.dart",
            "class WhisperGgmlLocalSttRuntime implements LocalSttRuntime",
            "getVersion()",
            ".transcribe(",
            "TranscribeRequest(",
            "WhisperModel.base",
            "WhisperVadMode.auto",
        ],
        "Local STT uses whisper_ggml_plus FFI runtime adapter",
    )
    require_snippets(
        reporter,
        service,
        [
            "abstract interface class LocalSttRuntime",
            "Future<bool> isRuntimeAvailable()",
            "throw StateError('오프라인 STT 런타임이 준비되지 않았습니다",
            "language: 'ko'",
        ],
        "Local STT service gates model readiness and FFI runtime availability",
    )
    require_snippets(
        reporter,
        provider,
        ["modelManagerProvider", "WhisperGgmlLocalSttRuntime"],
        "Local STT provider injects model manager and whisper runtime",
    )
    require_snippets(
        reporter,
        smoke,
        ["local_stt_smoke: PASS"],
        "Local STT smoke runner has a deterministic pass sentinel",
    )
    require_snippets(
        reporter,
        ios_pod_lock,
        ["whisper_ggml_plus", ".symlinks/plugins/whisper_ggml_plus/ios"],
        "iOS Pod lock includes whisper_ggml_plus native plugin",
    )
    require_snippets(
        reporter,
        macos_pod_lock,
        ["whisper_ggml_plus", ".symlinks/plugins/whisper_ggml_plus/macos"],
        "macOS Pod lock includes whisper_ggml_plus native plugin",
    )


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
        scheme for url_type in url_types for scheme in url_type.get("CFBundleURLSchemes", [])
    }
    if URL_SCHEME in schemes:
        reporter.ok(f"iOS URL scheme is {URL_SCHEME}")
    else:
        reporter.fail(f"iOS URL scheme {URL_SCHEME} missing")

    ats = info.get("NSAppTransportSecurity", {})
    if not isinstance(ats, dict):
        reporter.fail("iOS ATS configuration missing")
    elif ats.get("NSAllowsArbitraryLoads") is True:
        reporter.fail("iOS ATS must not allow arbitrary loads")
    else:
        insecure_domains = []
        exception_domains = ats.get("NSExceptionDomains", {})
        if isinstance(exception_domains, dict):
            for domain, config in exception_domains.items():
                if (
                    isinstance(config, dict)
                    and config.get("NSExceptionAllowsInsecureHTTPLoads") is True
                ):
                    insecure_domains.append(str(domain))
        if insecure_domains:
            reporter.fail(
                "iOS ATS must not allow insecure HTTP loads: "
                + ", ".join(sorted(insecure_domains))
            )
        else:
            reporter.ok("iOS ATS blocks arbitrary and insecure HTTP loads")

    document_types = info.get("CFBundleDocumentTypes", [])
    content_types = {
        content_type
        for document_type in document_types
        for content_type in document_type.get("LSItemContentTypes", [])
    }
    required_document_types = {
        "com.adobe.pdf",
        "org.openxmlformats.wordprocessingml.document",
        "public.image",
    }
    if required_document_types.issubset(content_types):
        reporter.ok("iOS document types accept PDF/DOCX/image Open In imports")
    else:
        missing = sorted(required_document_types - content_types)
        reporter.fail("iOS document import types missing: " + ", ".join(missing))

    entitlements = plistlib.loads(entitlements_path.read_bytes())
    aps_environment = entitlements.get("aps-environment")
    if aps_environment in {"development", "production"}:
        reporter.ok(f"iOS APNs entitlement is {aps_environment}")
        if aps_environment != "production":
            reporter.warn(
                "App Store distribution still requires production APNs entitlement from signing profile"
            )
    else:
        reporter.fail("iOS aps-environment entitlement missing")

    project = read_text(xcodeproj_path)
    if f"PRODUCT_BUNDLE_IDENTIFIER = {IOS_BUNDLE_ID};" in project:
        reporter.ok(f"iOS bundle id is {IOS_BUNDLE_ID}")
    else:
        reporter.fail(f"iOS bundle id {IOS_BUNDLE_ID} missing from project")
    deployment_targets = re.findall(r"IPHONEOS_DEPLOYMENT_TARGET = ([0-9]+(?:\.[0-9]+)?);", project)
    if not deployment_targets:
        reporter.fail("iOS deployment target missing from Xcode project")
    else:
        stale_targets = []
        for value in deployment_targets:
            major, _, minor = value.partition(".")
            parsed = (int(major), int(minor or "0"))
            if parsed < MIN_IOS_DEPLOYMENT_TARGET:
                stale_targets.append(value)
        if stale_targets:
            reporter.fail(
                "iOS deployment target must be at least 15.0: "
                + ", ".join(sorted(set(stale_targets)))
            )
        else:
            reporter.ok("iOS deployment target satisfies release support policy")
    if re.search(r"DEVELOPMENT_TEAM = [A-Z0-9]{10};", project):
        reporter.ok("iOS development team is configured in Xcode project")
    else:
        reporter.warn("iOS development team is not configured in Xcode project")

    app_delegate = read_text(app_delegate_path)
    recording_contract = [
        "FlutterMethodChannel(\n      name: channelName",
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
        reporter.ok(
            "iOS AppDelegate implements recording MethodChannel and AVAudioSession observers"
        )
    else:
        reporter.fail(
            "iOS AppDelegate recording contract missing: " + ", ".join(missing_recording_contract)
        )

    shared_import_contract = [
        'private let sharedImportChannelName = "com.voicetextnote.app/shared_import"',
        "consumeInitialSharedImport",
        "consumeLatestSharedImport",
        "override func application(",
        "sharedImportPayload(from: url)",
        "copySharedFile(_ url: URL)",
        'case "png":',
        '"filePath": target.path',
    ]
    missing_shared_import = [
        snippet for snippet in shared_import_contract if snippet not in app_delegate
    ]
    if not missing_shared_import:
        reporter.ok("iOS AppDelegate exposes shared import MethodChannel")
    else:
        reporter.fail(
            "iOS AppDelegate shared import contract missing: "
            + ", ".join(missing_shared_import)
        )


def check_android_project(root: Path, reporter: Reporter) -> None:
    gradle_path = root / "client/android/app/build.gradle"
    manifest_path = root / "client/android/app/src/main/AndroidManifest.xml"
    main_activity_path = root / (
        "client/android/app/src/main/kotlin/com/voicetextnote/app/MainActivity.kt"
    )
    network_path = root / "client/android/app/src/main/res/xml/network_security_config.xml"
    debug_network_path = root / "client/android/app/src/debug/res/xml/network_security_config.xml"
    for path, label in [
        (gradle_path, "Android app Gradle file"),
        (manifest_path, "Android manifest"),
        (main_activity_path, "Android MainActivity"),
        (network_path, "Android release/profile network security config"),
        (debug_network_path, "Android debug network security config"),
    ]:
        if not require_file(reporter, path, label):
            return
    gradle = read_text(gradle_path)
    if (
        f'applicationId "{ANDROID_PACKAGE}"' in gradle
        and f"namespace '{ANDROID_PACKAGE}'" in gradle
    ):
        reporter.ok(f"Android package/application id is {ANDROID_PACKAGE}")
    else:
        reporter.fail(f"Android package/application id {ANDROID_PACKAGE} missing")
    target_sdk_match = re.search(r"\btargetSdkVersion\s+(\d+)\b", gradle)
    if not target_sdk_match:
        reporter.fail("Android targetSdkVersion missing from Gradle config")
    else:
        target_sdk = int(target_sdk_match.group(1))
        if target_sdk >= MIN_GOOGLE_PLAY_TARGET_SDK:
            reporter.ok(
                "Android targetSdkVersion satisfies Google Play target API policy"
            )
        else:
            reporter.fail(
                "Android targetSdkVersion must be at least "
                f"{MIN_GOOGLE_PLAY_TARGET_SDK} for Google Play submissions"
            )

    manifest = read_text(manifest_path)
    if 'android:networkSecurityConfig="@xml/network_security_config"' in manifest:
        reporter.ok("Android manifest references network security config")
    else:
        reporter.fail("Android manifest does not reference network security config")
    if (
        "android.intent.action.SEND" in manifest
        and 'android:mimeType="text/plain"' in manifest
        and 'android:mimeType="application/pdf"' in manifest
        and 'android:mimeType="image/*"' in manifest
    ):
        reporter.ok("Android manifest accepts text/file share-sheet imports")
    else:
        reporter.fail("Android manifest missing ACTION_SEND text/file share import")

    main_activity = read_text(main_activity_path)
    shared_import_contract = [
        "com.voicetextnote.app/shared_import",
        "consumeInitialSharedImport",
        "consumeLatestSharedImport",
        "Intent.ACTION_SEND",
        "Intent.EXTRA_TEXT",
        "Intent.EXTRA_STREAM",
        "OpenableColumns.DISPLAY_NAME",
        "filePath",
    ]
    missing_shared_import = [
        snippet for snippet in shared_import_contract if snippet not in main_activity
    ]
    if not missing_shared_import:
        reporter.ok("Android MainActivity exposes shared import MethodChannel")
    else:
        reporter.fail(
            "Android MainActivity shared import contract missing: "
            + ", ".join(missing_shared_import)
        )

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
    debug_cleartext_hosts = set(re.findall(r"<domain\b[^>]*>([^<]+)</domain>", debug_network))
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


def check_tone_release_policy(root: Path, reporter: Reporter) -> None:
    config_path = root / "backend/app/config.py"
    pyproject_path = root / "pyproject.toml"
    readme_path = root / "README.md"
    for path, label in [
        (config_path, "Backend config"),
        (pyproject_path, "Python project metadata"),
        (readme_path, "README"),
    ]:
        if not require_file(reporter, path, label):
            return

    config = read_text(config_path)
    if 'tone_model: str = ""' in config:
        reporter.ok("Tone analysis is disabled by default when tone_model is empty")
    else:
        reporter.fail("Tone analysis must default to disabled with tone_model empty")

    pyproject = read_text(pyproject_path)
    require_snippets(
        reporter,
        pyproject,
        [
            "opensmile>=2.6.0",
            "opensmile은 AGPL-3.0",
            "로컬 전용 처리 환경에서만 사용",
            "네트워크 서비스 형태 외부 제공 금지",
        ],
        "Python dependency policy documents opensmile AGPL local-only constraints",
    )

    readme = read_text(readme_path)
    require_snippets(
        reporter,
        readme,
        [
            "로컬 전용 처리",
            "opensmile",
            "AGPL-3.0",
            "네트워크 서비스",
            "SaaS",
        ],
        "README documents opensmile AGPL local-only and SaaS review policy",
    )


def check_readme_release_status(root: Path, reporter: Reporter) -> None:
    path = root / "README.md"
    if not require_file(reporter, path, "README"):
        return
    readme = read_text(path)
    completed_spec_count = len(re.findall(r"^✅ SPEC-", readme, re.MULTILINE))
    require_snippets(
        reporter,
        readme,
        [
            "Release Candidate",
            "strict 실기기 release evidence 대기",
            "RELEASE_E2E_EVIDENCE_PATH",
        ],
        "README distinguishes automated readiness from final physical release readiness",
    )
    if re.search(r"Production Ready \(\d+/\d+ SPECs 완료\)", readme):
        reporter.fail(
            "README must not claim Production Ready before strict release evidence passes"
        )
    else:
        reporter.ok("README does not overclaim Production Ready before strict evidence")
    if (
        f"{CURRENT_BACKEND_TEST_COUNT} 백엔드 테스트" in readme
        and f"{CURRENT_BACKEND_TEST_COUNT}개" in readme
        and (
            f"Flutter {CURRENT_FLUTTER_TEST_COUNT}" in readme
            or f"{CURRENT_FLUTTER_TEST_COUNT}개" in readme
        )
        and f"{CURRENT_TOTAL_TEST_COUNT}개" in readme
    ):
        reporter.ok("README test counts match current release validation evidence")
    else:
        reporter.fail(
            "README test counts must match current "
            f"{CURRENT_BACKEND_TEST_COUNT} backend / "
            f"{CURRENT_FLUTTER_TEST_COUNT} Flutter / "
            f"{CURRENT_TOTAL_TEST_COUNT} total evidence"
        )
    if "`flutter build apk --release`" in readme and "`flutter build apk --debug`" not in readme:
        reporter.ok("README Android RC status references release APK verification")
    else:
        reporter.fail("README Android RC status must reference release APK verification")
    require_snippets(
        reporter,
        readme,
        [
            "ANDROID_KEYSTORE_BASE64",
            "ANDROID_KEYSTORE_PASSWORD",
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASSWORD",
            "REQUIRE_ANDROID_RELEASE_SIGNING=true",
        ],
        "README strict gate must document Android release signing",
    )
    if "RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.example.json" in readme:
        reporter.fail("README strict command must not use example release E2E evidence")
    elif "RELEASE_E2E_EVIDENCE_PATH=docs/release-e2e-evidence.json" in readme:
        reporter.ok("README strict command uses real release E2E evidence path")
    else:
        reporter.fail("README strict command must set RELEASE_E2E_EVIDENCE_PATH")
    if f"{completed_spec_count}개 SPEC" in readme:
        reporter.fail("README should avoid hard-coded completed SPEC counts outside the SPEC list")
    else:
        reporter.ok("README avoids hard-coded completed SPEC counts outside the SPEC list")


def check_docs(root: Path, reporter: Reporter) -> None:
    required = [
        (root / "docs/firebase-setup-guide.md", "Firebase setup guide"),
        (root / "docs/e2e-device-checklist.md", "Device E2E checklist"),
        (root / "docs/release-procedure.md", "Release procedure"),
        (root / "docs/app-store-metadata.md", "App Store metadata"),
        (root / "docs/privacy-policy.md", "Privacy policy"),
        (root / "docs/screenshot-guide.md", "Screenshot guide"),
    ]
    for path, label in required:
        if not require_file(reporter, path, label):
            return
    firebase_doc = read_text(root / "docs/firebase-setup-guide.md")
    for snippet in [
        "FIREBASE_CREDENTIALS_PATH",
        "APNs",
        "google-services.json",
        "GoogleService-Info.plist",
    ]:
        if snippet in firebase_doc:
            reporter.ok(f"Firebase guide documents {snippet}")
        else:
            reporter.fail(f"Firebase guide missing {snippet}")
    e2e_doc = read_text(root / "docs/e2e-device-checklist.md")
    e2e_requirements = [
        ("Push/푸시 알림", ("Push", "푸시 알림")),
        ("백그라운드 녹음", ("백그라운드 녹음",)),
        ("create_release_e2e_evidence.py", ("create_release_e2e_evidence.py",)),
        ("verify_mobile_release_runner.py", ("verify_mobile_release_runner.py",)),
        ("xcodebuild -version", ("xcodebuild -version",)),
        ("./scripts/verify_mobile.sh --native", ("./scripts/verify_mobile.sh --native",)),
        (
            "REQUIRE_ANDROID_RELEASE_SIGNING",
            ("REQUIRE_ANDROID_RELEASE_SIGNING", "Android release signing gate"),
        ),
        (
            "IOS_RELEASE_ENTITLEMENTS_PATH",
            ("IOS_RELEASE_ENTITLEMENTS_PATH", "ios-release-entitlements.plist"),
        ),
        ("RELEASE_E2E_EVIDENCE_PATH", ("RELEASE_E2E_EVIDENCE_PATH",)),
        ("artifact_sha256", ("artifact_sha256", "SHA-256")),
        ("Android release APK", ("app-release.apk", "Android release APK")),
        ("Swift Package Manager warning", ("Swift Package Manager", "whisper_ggml_plus")),
    ]
    for label, snippets in e2e_requirements:
        if any(snippet in e2e_doc for snippet in snippets):
            reporter.ok(f"E2E checklist covers {label}")
        else:
            reporter.fail(f"E2E checklist missing {label}")
    procedure_doc = read_text(root / "docs/release-procedure.md")
    readme = read_text(root / "README.md")
    completed_spec_count = len(re.findall(r"^✅ SPEC-", readme, re.MULTILINE))
    version_match = re.search(r"\*\*버전\*\*:\s*([0-9]+\.[0-9]+\.[0-9]+)", readme)
    current_version = version_match.group(1) if version_match else ""
    require_snippets(
        reporter,
        procedure_doc,
        [
            f"**{EXPECTED_STRICT_MISSING_INPUT_ERRORS} errors",
            "client/scripts/create_release_e2e_evidence.py",
            "17개 required scenario",
            "python3 client/scripts/verify_mobile_release_runner.py",
            "python3 client/scripts/verify_github_mobile_release_env.py",
            "python3 client/scripts/verify_release_readiness.py --strict",
            "REQUIRE_ANDROID_RELEASE_SIGNING=true",
            "IOS_RELEASE_ENTITLEMENTS_PATH",
            "ios-release-entitlements.plist",
            "aps-environment",
            "get-task-allow",
            "`platforms`",
            '["android", "ios"]',
            '["android"]',
            '["ios"]',
        ],
        "Release procedure matches current strict E2E evidence workflow",
    )
    if re.search(r"(?<!client/)scripts/create_release_e2e_evidence\.py", procedure_doc):
        reporter.fail("Release procedure references obsolete release evidence script path")
    else:
        reporter.ok("Release procedure uses current release evidence script path")
    if "evidence JSON 6개" in procedure_doc or "6개 시나리오" in procedure_doc:
        reporter.fail("Release procedure references obsolete 6-scenario evidence schema")
    else:
        reporter.ok("Release procedure uses current 17-scenario evidence schema")
    expected_spec_text = f"{completed_spec_count}개 SPEC 전부 완료"
    expected_tag_text = f"{completed_spec_count} SPECs completed"
    if expected_spec_text in procedure_doc and expected_tag_text in procedure_doc:
        reporter.ok("Release procedure SPEC count matches README completed SPEC list")
    else:
        reporter.fail(
            "Release procedure SPEC count must match README completed SPEC list "
            f"({completed_spec_count})"
        )
    if (
        f"{CURRENT_BACKEND_TEST_COUNT} passed" in procedure_doc
        and f"Flutter: {CURRENT_FLUTTER_TEST_COUNT} passed" in procedure_doc
    ):
        reporter.ok("Release procedure backend test count matches latest full pytest evidence")
    else:
        reporter.fail(
            "Release procedure test counts must match latest "
            f"{CURRENT_BACKEND_TEST_COUNT} backend / {CURRENT_FLUTTER_TEST_COUNT} Flutter evidence"
        )
    if (
        "`verify_mobile_release_runner.py` PASS" in procedure_doc
        and "`verify_github_mobile_release_env.py` PASS" in procedure_doc
    ):
        reporter.ok("Release procedure checklist requires runner and GitHub environment preflights")
    else:
        reporter.fail(
            "Release procedure checklist must require runner and GitHub environment preflights"
        )
    if current_version and all(
        snippet in procedure_doc
        for snippet in (
            f"Production Ready v{current_version}",
            f"git tag v{current_version}",
            f"gh release create v{current_version}",
            f"--title \"v{current_version} — Production Ready\"",
        )
    ):
        reporter.ok("Release procedure version matches README current version")
    else:
        reporter.fail("Release procedure version must match README current version")
    app_store_doc = read_text(root / "docs/app-store-metadata.md")
    for snippet in [
        "App Store Connect",
        "Google Play Console",
        "Privacy Policy",
        "com.voicetextnote.app",
        "iPhone 6.7",
        "iPad Pro",
        "Android",
        "https://voicetextnote.com/privacy",
        "RELEASE_E2E_EVIDENCE_PATH",
    ]:
        if snippet in app_store_doc:
            reporter.ok(f"App Store metadata covers {snippet}")
        else:
            reporter.fail(f"App Store metadata missing {snippet}")
    if re.search(r"to be configured|TBD|TODO", app_store_doc, re.IGNORECASE):
        reporter.fail("App Store metadata contains unresolved store listing placeholder")
    else:
        reporter.ok("App Store metadata has no unresolved store listing placeholders")

    screenshot_doc = read_text(root / "docs/screenshot-guide.md")
    screenshot_requirements = [
        "iPhone 6.7",
        "iPhone 6.5",
        "iPad 12.9",
        "Phone",
        "Tablet",
        "홈 화면",
        "녹음 화면",
        "결과 화면",
        "검색/내보내기",
    ]
    for snippet in screenshot_requirements:
        if snippet in screenshot_doc:
            reporter.ok(f"Screenshot guide covers {snippet}")
        else:
            reporter.fail(f"Screenshot guide missing {snippet}")

    privacy_doc = read_text(root / "docs/privacy-policy.md")
    privacy_requirements = [
        "Audio Recordings",
        "Push Notification Token",
        "Firebase Cloud Messaging",
        "OpenAI API",
        "Data Used for Tracking: None",
        "privacy@voicetextnote.com",
    ]
    for snippet in privacy_requirements:
        if snippet in privacy_doc:
            reporter.ok(f"Privacy policy covers {snippet}")
        else:
            reporter.fail(f"Privacy policy missing {snippet}")

    check_png_icon(
        reporter,
        root / "client/assets/icon/app_icon_no_alpha.png",
        "Store app icon",
        (1024, 1024),
        allow_alpha=False,
    )
    check_png_icon(
        reporter,
        root / "client/ios/Runner/Assets.xcassets/AppIcon.appiconset/Icon-App-1024x1024@1x.png",
        "iOS AppIcon 1024",
        (1024, 1024),
        allow_alpha=False,
    )


def check_owll_benchmark_doc(root: Path, reporter: Reporter) -> None:
    path = root / "docs/owll-benchmark-prd.md"
    if not require_file(reporter, path, "Owll benchmark PRD"):
        return
    content = read_text(path)
    require_snippets(
        reporter,
        content,
        [
            "**Last verified**: 2026-06-22",
            "https://apps.apple.com/us/app/owll-ai-note-taker-assistant/id6450300197",
            "https://play.google.com/store/apps/details?id=com.hmd.quickrecorder",
            "https://owll.ai/blog/ai-note-taker-for-teams",
            "3.16.0",
            "4.2 star rating",
            "354 reviews",
            "100K+ downloads",
            "Jun 11, 2026",
            "Jun 17, 2026",
            "900 minutes per month",
            "100+ languages",
            "10+ summary modes",
            "Ask AI across notes",
            "Data safety",
            "privacy-first differentiation",
            "Source discrepancy to monitor",
        ],
        "Owll benchmark PRD captures current competitor evidence and gaps",
    )


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


def check_tracked_release_e2e_scaffold(root: Path, reporter: Reporter) -> None:
    path = root / "docs/release-e2e-evidence.json"
    if not require_file(reporter, path, "Tracked release E2E evidence scaffold"):
        return
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        reporter.fail(f"Tracked release E2E evidence scaffold JSON is invalid: {exc}")
        return
    expected_top_level_keys = {
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
    actual_top_level_keys = set(data) if isinstance(data, dict) else set()
    if actual_top_level_keys == expected_top_level_keys:
        reporter.ok("Tracked release E2E evidence scaffold matches strict schema keys")
    else:
        missing = ", ".join(sorted(expected_top_level_keys - actual_top_level_keys)) or "none"
        extra = ", ".join(sorted(actual_top_level_keys - expected_top_level_keys)) or "none"
        reporter.fail(
            "Tracked release E2E evidence scaffold schema keys are stale "
            f"(missing: {missing}; extra: {extra})"
        )
    scenarios = data.get("scenarios") if isinstance(data, dict) else None
    if not isinstance(scenarios, dict):
        reporter.fail("Tracked release E2E evidence scaffold missing scenario results")
        return
    artifacts = data.get("artifacts")
    artifact_hashes = data.get("artifact_sha256")
    if isinstance(artifacts, dict) and isinstance(artifact_hashes, dict):
        if set(artifact_hashes) == set(artifacts):
            reporter.ok("Tracked release E2E evidence scaffold hashes every artifact key")
        else:
            missing = ", ".join(sorted(set(artifacts) - set(artifact_hashes))) or "none"
            extra = ", ".join(sorted(set(artifact_hashes) - set(artifacts))) or "none"
            reporter.fail(
                "Tracked release E2E evidence scaffold artifact hash keys are stale "
                f"(missing: {missing}; extra: {extra})"
            )
    else:
        reporter.fail("Tracked release E2E evidence scaffold missing artifact hashes")
    release_gate = data.get("release_gate") if isinstance(data, dict) else None
    if not isinstance(release_gate, dict):
        reporter.fail("Tracked release E2E evidence scaffold missing release gate metadata")
    elif release_gate == {
        "android_release_signing": True,
        "ios_production_entitlements": True,
        "ios_entitlements_sha256": "0" * 64,
    }:
        reporter.ok(
            "Tracked release E2E evidence scaffold records signed mobile release gates"
        )
    else:
        reporter.fail(
            "Tracked release E2E evidence scaffold release gate metadata is stale"
        )
    if isinstance(artifacts, dict):
        for key in sorted(set(artifacts) & {"android_apk", "ios_runner_app"}):
            artifact_path = artifacts.get(key)
            if isinstance(artifact_path, str):
                contract_error = release_artifact_path_contract_error(root, key, artifact_path)
                if contract_error:
                    reporter.fail(
                        "Tracked release E2E evidence scaffold "
                        f"{contract_error}"
                    )
                else:
                    reporter.ok(
                        f"Tracked release E2E evidence scaffold artifact path contract: {key}"
                    )
            else:
                reporter.fail(
                    "Tracked release E2E evidence scaffold artifact path must be a string: "
                    f"{key}"
                )
    actual = set(scenarios)
    expected = set(REQUIRED_E2E_SCENARIOS)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        extra = ", ".join(sorted(actual - expected)) or "none"
        reporter.fail(
            "Tracked release E2E evidence scaffold scenario keys are stale "
            f"(missing: {missing}; extra: {extra})"
        )
        return
    reporter.ok("Tracked release E2E evidence scaffold lists every required scenario")

    stale_platform_scenarios = []
    for key in sorted(REQUIRED_E2E_SCENARIOS):
        scenario = scenarios.get(key)
        platforms = scenario.get("platforms") if isinstance(scenario, dict) else None
        expected_platforms = list(REQUIRED_E2E_SCENARIO_PLATFORMS[key])
        if platforms != expected_platforms:
            stale_platform_scenarios.append(key)
    if stale_platform_scenarios:
        reporter.fail(
            "Tracked release E2E evidence scaffold scenario platforms are stale: "
            + ", ".join(stale_platform_scenarios)
        )
    else:
        reporter.ok("Tracked release E2E evidence scaffold scenario platforms match contract")


def check_service_account(path: Path, reporter: Reporter) -> None:
    if not path.is_file():
        reporter.fail(f"FIREBASE_CREDENTIALS_PATH does not point to a file: {path}")
        return
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        reporter.fail(f"Firebase service account JSON is invalid: {exc}")
        return
    if not isinstance(data, dict):
        reporter.fail("Firebase service account JSON must be an object")
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
    if not isinstance(private_key, str):
        reporter.fail("Firebase service account private_key must be a string")
    elif (
        "-----BEGIN PRIVATE KEY-----" in private_key
        and "-----END PRIVATE KEY-----" in private_key
    ):
        reporter.ok("Firebase service account private key is present")
    else:
        reporter.fail("Firebase service account private key missing")
    if not isinstance(client_email, str):
        reporter.fail("Firebase service account client_email must be a string")
    elif client_email.endswith(f"@{PROJECT_ID}.iam.gserviceaccount.com"):
        reporter.ok("Firebase service account client_email is present")
    else:
        reporter.fail("Firebase service account client_email missing or invalid")


def require_env_file(
    reporter: Reporter, env_name: str, label: str, suffix: str | None = None
) -> None:
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


def require_env_private_key_file(
    reporter: Reporter, env_name: str, label: str, suffix: str = ".p8"
) -> None:
    value = os.environ.get(env_name, "")
    if not value:
        reporter.fail(f"{label}: {env_name} is not set")
        return
    path = Path(value).expanduser()
    if path.suffix != suffix:
        reporter.fail(f"{label}: {env_name} must point to a {suffix} file")
        return
    if not path.is_file():
        reporter.fail(f"{label}: {env_name} file missing at {path}")
        return
    key_text = read_text(path).strip()
    if (
        "-----BEGIN PRIVATE KEY-----" in key_text
        and "-----END PRIVATE KEY-----" in key_text
    ):
        reporter.ok(f"{label}: {env_name} private key is present")
    else:
        reporter.fail(f"{label}: {env_name} private key PEM is invalid")


def require_env_value(
    reporter: Reporter, env_name: str, label: str, pattern: str | None = None
) -> None:
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
        reporter.fail(
            "Android physical test device serial: adb devices failed or adb is unavailable"
        )
        return
    connected_serials = {
        line.split()[0]
        for line in output.splitlines()
        if re.match(r"^\S+\s+device\b", line)
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
        reporter.fail(
            "iOS physical test device UDID: xcrun devicectl failed or Xcode tools are unavailable"
        )
        return
    matching_lines = [line for line in output.splitlines() if udid in line]
    if matching_lines and any(re.search(r"\savailable\s", line) for line in matching_lines):
        reporter.ok("iOS physical test device UDID is connected and available")
    elif matching_lines:
        reporter.fail(f"iOS physical test device UDID {udid} is known but not available")
    else:
        reporter.fail(f"iOS physical test device UDID {udid} is not visible to xcrun devicectl")


def check_ios_release_entitlements(entitlements_path: Path, reporter: Reporter) -> None:
    if not require_file(reporter, entitlements_path, "iOS release entitlements evidence"):
        return
    try:
        entitlements = plistlib.loads(entitlements_path.read_bytes())
    except (plistlib.InvalidFileException, ValueError) as exc:
        reporter.fail(f"iOS release entitlements evidence plist is invalid: {exc}")
        return
    if not isinstance(entitlements, dict):
        reporter.fail("iOS release entitlements evidence must be a plist dictionary")
        return

    aps_environment = entitlements.get("aps-environment")
    if aps_environment == "production":
        reporter.ok("iOS release entitlements use production APNs environment")
    else:
        reporter.fail("iOS release entitlements must use production APNs environment")

    get_task_allow = entitlements.get("get-task-allow")
    if get_task_allow is False:
        reporter.ok("iOS release entitlements disable debugger attachment")
    else:
        reporter.fail("iOS release entitlements must set get-task-allow to false")

    team_id = os.environ.get("APNS_TEAM_ID", "")
    entitlement_team = entitlements.get("com.apple.developer.team-identifier")
    if team_id and entitlement_team == team_id:
        reporter.ok("iOS release entitlements team identifier matches APNs team")
    elif team_id:
        reporter.fail("iOS release entitlements team identifier does not match APNs team")

    application_id = entitlements.get("application-identifier")
    expected_app_id = f"{team_id}.{IOS_BUNDLE_ID}" if team_id else ""
    if expected_app_id and application_id == expected_app_id:
        reporter.ok("iOS release entitlements application identifier matches bundle id")
    elif expected_app_id:
        reporter.fail(
            "iOS release entitlements application identifier does not match bundle id"
        )


def require_non_empty_mapping(
    reporter: Reporter, data: dict[str, object], key: str, label: str
) -> dict[str, object]:
    value = data.get(key)
    if isinstance(value, dict) and value:
        reporter.ok(f"Release E2E evidence includes {label}")
        return value
    reporter.fail(f"Release E2E evidence missing {label}")
    return {}


def require_non_empty_string(
    reporter: Reporter, data: dict[str, object], key: str, label: str
) -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        reporter.ok(f"Release E2E evidence includes {label}")
        return value.strip()
    if key in data:
        reporter.fail(f"Release E2E evidence {label} must be a string")
        return ""
    reporter.fail(f"Release E2E evidence missing {label}")
    return ""


def require_iso_datetime(
    reporter: Reporter, data: dict[str, object], key: str, label: str
) -> str:
    value = require_non_empty_string(reporter, data, key, label)
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        reporter.fail(f"Release E2E evidence {label} must be ISO-8601")
        return ""
    reporter.ok(f"Release E2E evidence {label} is ISO-8601")
    if parsed.tzinfo is None:
        reporter.fail(f"Release E2E evidence {label} must include timezone")
        comparable = parsed.replace(tzinfo=UTC)
    else:
        comparable = parsed
    now = datetime.now(UTC)
    if comparable > now:
        reporter.fail(f"Release E2E evidence {label} must not be in the future")
    elif now - comparable > MAX_RELEASE_E2E_EVIDENCE_AGE:
        reporter.fail(f"Release E2E evidence {label} is stale")
    return value


def require_git_revision(
    reporter: Reporter, data: dict[str, object], key: str, label: str
) -> str:
    value = require_non_empty_string(reporter, data, key, label)
    if not value:
        return ""
    if re.fullmatch(r"git:[0-9a-fA-F]{7,40}", value):
        reporter.ok(f"Release E2E evidence {label} is a git revision")
        return value
    reporter.fail(f"Release E2E evidence {label} must be git:<sha>")
    return ""


def current_git_revision(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "git:unknown"
    revision = completed.stdout.strip()
    return f"git:{revision}" if revision else "git:unknown"


def has_unresolved_evidence_placeholder(value: str) -> bool:
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in UNRESOLVED_EVIDENCE_PATTERNS)


def normalize_evidence_note(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def has_observation_artifact_marker(value: str) -> bool:
    return any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in RELEASE_E2E_OBSERVATION_ARTIFACT_PATTERNS
    )


def has_observation_artifact_reference(value: str) -> bool:
    return any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in RELEASE_E2E_OBSERVATION_REFERENCE_PATTERNS
    )


def observation_artifact_references(value: str) -> set[str]:
    references: set[str] = set()
    for pattern in RELEASE_E2E_OBSERVATION_REFERENCE_PATTERNS:
        for match in re.finditer(pattern, value, re.IGNORECASE):
            references.add(match.group(0).rstrip(".,);]").casefold())
    return references


def has_scenario_observation_artifact_reference(value: str, scenario_key: str) -> bool:
    scenario_key = scenario_key.casefold()
    return any(scenario_key in reference for reference in observation_artifact_references(value))


def resolve_release_artifact_path(root: Path, artifact_path: str) -> Path:
    path = Path(artifact_path).expanduser()
    if path.is_absolute():
        return path
    return root / path


def artifact_path_stays_inside_root(root: Path, artifact_path: str) -> bool:
    path = Path(artifact_path).expanduser()
    try:
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        resolved.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_release_evidence_path(root: Path, evidence_path: str) -> Path:
    path = Path(evidence_path).expanduser()
    if path.is_absolute():
        return path
    return root / path


def evidence_path_stays_inside_root(root: Path, evidence_path: str) -> bool:
    try:
        resolved = resolve_release_evidence_path(root, evidence_path).resolve()
        resolved.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def release_artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if path.is_dir():
        for file_path in sorted(child for child in path.rglob("*") if child.is_file()):
            digest.update(file_path.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(file_path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    return ""


def is_sha256_hex(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))


def is_android_apk(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as apk:
            names = set(apk.namelist())
            return "AndroidManifest.xml" in names and any(
                re.fullmatch(r"classes(?:\d*)\.dex", name) for name in names
            )
    except zipfile.BadZipFile:
        return False


def has_apk_v1_signature(names: set[str]) -> bool:
    signature_files = {
        name.upper()
        for name in names
        if name.upper().startswith("META-INF/") and not name.endswith("/")
    }
    has_signature_manifest = any(name.endswith(".SF") for name in signature_files)
    has_signature_block = any(
        name.endswith((".RSA", ".DSA", ".EC")) for name in signature_files
    )
    return has_signature_manifest and has_signature_block


def has_apk_signing_block(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    eocd_offset = data.rfind(b"PK\x05\x06")
    if eocd_offset == -1 or eocd_offset + 20 > len(data):
        return False
    central_directory_offset = struct.unpack_from("<I", data, eocd_offset + 16)[0]
    if central_directory_offset < 24 or central_directory_offset > len(data):
        return False
    if (
        data[
            central_directory_offset
            - len(APK_SIGNATURE_BLOCK_MAGIC) : central_directory_offset
        ]
        != APK_SIGNATURE_BLOCK_MAGIC
    ):
        return False
    signing_block_size = struct.unpack_from(
        "<Q", data, central_directory_offset - len(APK_SIGNATURE_BLOCK_MAGIC) - 8
    )[0]
    signing_block_start = central_directory_offset - signing_block_size - 8
    if signing_block_start < 0 or signing_block_start + 8 > len(data):
        return False
    return (
        struct.unpack_from("<Q", data, signing_block_start)[0]
        == signing_block_size
    )


def is_signed_android_apk(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as apk:
            names = set(apk.namelist())
    except zipfile.BadZipFile:
        return False
    return has_apk_v1_signature(names) or has_apk_signing_block(path)


def ios_app_metadata(path: Path) -> dict[str, str]:
    try:
        with (path / "Info.plist").open("rb") as plist:
            data = plistlib.load(plist)
    except (OSError, plistlib.InvalidFileException):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        "bundle_id": str(data.get("CFBundleIdentifier", "")).strip(),
        "executable": str(data.get("CFBundleExecutable", "")).strip(),
    }


def release_artifact_path_contract_error(
    root: Path, key: str, artifact_path: str
) -> str | None:
    artifact_suffixes = {
        "android_apk": ".apk",
        "ios_runner_app": ".app",
    }
    if Path(artifact_path).expanduser().is_absolute():
        return f"artifact path must be repo-relative: {key}"
    if not artifact_path_stays_inside_root(root, artifact_path):
        return f"artifact path must stay inside repo: {key}"
    resolved_artifact = resolve_release_artifact_path(root, artifact_path)
    expected_suffix = artifact_suffixes[key]
    if resolved_artifact.suffix != expected_suffix:
        return f"artifact path must end with {expected_suffix}: {key}"
    if key == "android_apk":
        artifact_name = resolved_artifact.name.lower()
        if "debug" in artifact_name or "release" not in artifact_name:
            return f"artifact must be a release APK: {key}"
    if artifact_path != CANONICAL_RELEASE_ARTIFACT_PATHS[key]:
        return f"artifact path must match canonical release output: {key}"
    return None


def release_artifact_structure_error(root: Path, key: str, artifact_path: str) -> str | None:
    artifact_type_checks = {
        "android_apk": Path.is_file,
        "ios_runner_app": Path.is_dir,
    }
    contract_error = release_artifact_path_contract_error(root, key, artifact_path)
    if contract_error:
        return contract_error
    resolved_artifact = resolve_release_artifact_path(root, artifact_path)
    type_check = artifact_type_checks[key]
    if type_check(resolved_artifact):
        if key == "android_apk" and resolved_artifact.stat().st_size == 0:
            return f"artifact must be non-empty: {key}"
        if key == "android_apk" and not is_android_apk(resolved_artifact):
            return f"artifact must be a valid APK zip: {key}"
        if key == "android_apk" and not is_signed_android_apk(resolved_artifact):
            return f"artifact must be signed: {key}"
        if key == "ios_runner_app" and not (resolved_artifact / "Info.plist").is_file():
            return f"artifact missing Info.plist: {key}"
        if key == "ios_runner_app":
            metadata = ios_app_metadata(resolved_artifact)
            if metadata.get("bundle_id") != IOS_BUNDLE_ID:
                return f"artifact bundle id mismatch: {key}"
            executable = metadata.get("executable", "")
            if not executable or not (resolved_artifact / executable).is_file():
                return f"artifact missing executable: {key}"
        return None
    if resolved_artifact.exists():
        expected_type = "file" if key == "android_apk" else "directory"
        return f"artifact must be a {expected_type}: {key}"
    return f"artifact missing on disk: {key}"


def check_release_e2e_evidence(path: Path, reporter: Reporter, root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parents[2]
    if not path.is_file():
        reporter.fail(f"RELEASE_E2E_EVIDENCE_PATH does not point to a file: {path}")
        return
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        reporter.fail(f"Release E2E evidence JSON is invalid: {exc}")
        return
    if not isinstance(data, dict):
        reporter.fail("Release E2E evidence must be a JSON object")
        return

    expected_top_level_keys = {
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
    for key in sorted(set(data) - expected_top_level_keys):
        reporter.fail(f"Release E2E evidence includes unknown top-level key: {key}")

    require_iso_datetime(reporter, data, "tested_at", "test timestamp")
    tester = require_non_empty_string(reporter, data, "tester", "tester")
    if tester and has_unresolved_evidence_placeholder(tester):
        reporter.fail("Release E2E evidence tester contains unresolved placeholder")
    current_revision = current_git_revision(root)
    for key, label in [
        ("backend_version", "backend version"),
        ("client_version", "client version"),
    ]:
        revision = require_git_revision(reporter, data, key, label)
        if not revision or current_revision == "git:unknown":
            continue
        if revision == current_revision:
            reporter.ok(f"Release E2E evidence {label} matches current git revision")
        else:
            reporter.fail(
                f"Release E2E evidence {label} does not match current git revision"
            )

    release_gate = require_non_empty_mapping(
        reporter, data, "release_gate", "release gate metadata"
    )
    if release_gate:
        expected_release_gate_keys = {
            "android_release_signing",
            "ios_entitlements_sha256",
            "ios_production_entitlements",
        }
        for key in sorted(set(release_gate) - expected_release_gate_keys):
            reporter.fail(f"Release E2E evidence includes unknown release gate: {key}")
        if release_gate.get("android_release_signing") is True:
            reporter.ok("Release E2E evidence records signed Android release gate")
        else:
            reporter.fail(
                "Release E2E evidence must record signed Android release gate"
            )
        if release_gate.get("ios_production_entitlements") is True:
            reporter.ok("Release E2E evidence records production iOS entitlement gate")
        else:
            reporter.fail(
                "Release E2E evidence must record production iOS entitlement gate"
            )
        ios_entitlements_hash = release_gate.get("ios_entitlements_sha256")
        if isinstance(ios_entitlements_hash, str):
            expected_hash = ios_entitlements_hash.strip()
            if not expected_hash:
                reporter.fail(
                    "Release E2E evidence must record iOS entitlements SHA-256"
                )
            elif not is_sha256_hex(expected_hash):
                reporter.fail(
                    "Release E2E evidence iOS entitlements hash must be lowercase "
                    "SHA-256 hex"
                )
            else:
                ios_entitlements_path = os.environ.get("IOS_RELEASE_ENTITLEMENTS_PATH", "")
                if ios_entitlements_path:
                    resolved_entitlements = resolve_release_evidence_path(
                        root, ios_entitlements_path
                    )
                    actual_hash = release_artifact_sha256(resolved_entitlements)
                    if actual_hash == expected_hash:
                        reporter.ok(
                            "Release E2E evidence iOS entitlements hash matches strict env"
                        )
                    else:
                        reporter.fail(
                            "Release E2E evidence iOS entitlements hash mismatch"
                        )
                else:
                    reporter.ok("Release E2E evidence records iOS entitlements hash")
        else:
            reporter.fail("Release E2E evidence iOS entitlements hash must be a string")

    devices = require_non_empty_mapping(reporter, data, "devices", "device metadata")
    expected_device_platforms = {"android", "ios"}
    evidence_device_ids: dict[str, str] = {}
    if devices:
        for platform in sorted(set(devices) - expected_device_platforms):
            reporter.fail(
                f"Release E2E evidence includes unknown device platform: {platform}"
            )
    for platform, expected_id in [
        ("android", os.environ.get("ANDROID_DEVICE_SERIAL", "")),
        ("ios", os.environ.get("IOS_DEVICE_UDID", "")),
    ]:
        device = devices.get(platform) if isinstance(devices, dict) else None
        if not isinstance(device, dict):
            reporter.fail(f"Release E2E evidence missing {platform} device metadata")
            continue
        id_key = "serial" if platform == "android" else "udid"
        expected_device_keys = {id_key, "model", "os_version"}
        for key in sorted(set(device) - expected_device_keys):
            reporter.fail(
                f"Release E2E evidence includes unknown {platform} device metadata key: {key}"
            )
        actual_id = require_non_empty_string(
            reporter, device, id_key, f"{platform} device {id_key}"
        )
        if actual_id and actual_id == expected_id:
            reporter.ok(f"Release E2E evidence {platform} device matches strict env")
            evidence_device_ids[platform] = actual_id
        else:
            reporter.fail(
                f"Release E2E evidence {platform} device {id_key} does not match strict env"
            )
        for key in ["model", "os_version"]:
            device_value = require_non_empty_string(
                reporter, device, key, f"{platform} device {key}"
            )
            if device_value and has_unresolved_evidence_placeholder(device_value):
                reporter.fail(
                    f"Release E2E evidence {platform} device {key} "
                    "contains unresolved placeholder"
                )

    artifacts = require_non_empty_mapping(reporter, data, "artifacts", "build artifacts")
    artifact_hashes = require_non_empty_mapping(
        reporter, data, "artifact_sha256", "artifact hashes"
    )
    expected_artifact_keys = {"android_apk", "ios_runner_app"}
    if artifacts:
        for key in sorted(set(artifacts) - expected_artifact_keys):
            reporter.fail(f"Release E2E evidence includes unknown artifact: {key}")
    if artifact_hashes:
        for key in sorted(set(artifact_hashes) - expected_artifact_keys):
            reporter.fail(f"Release E2E evidence includes unknown artifact hash: {key}")
    for key in sorted(expected_artifact_keys):
        artifact_value = artifacts.get(key, "") if artifacts else ""
        if not isinstance(artifact_value, str):
            reporter.fail(f"Release E2E evidence artifact path must be a string: {key}")
            continue
        artifact_path = artifact_value.strip()
        if not artifact_path:
            reporter.fail(f"Release E2E evidence missing artifact {key}")
            continue
        structure_error = release_artifact_structure_error(root, key, artifact_path)
        if structure_error:
            reporter.fail(f"Release E2E evidence {structure_error}")
            continue
        resolved_artifact = resolve_release_artifact_path(root, artifact_path)
        hash_value = artifact_hashes.get(key, "") if artifact_hashes else ""
        if not isinstance(hash_value, str):
            reporter.fail(f"Release E2E evidence artifact hash must be a string: {key}")
            continue
        expected_hash = hash_value.strip()
        if not expected_hash:
            reporter.fail(f"Release E2E evidence missing artifact hash: {key}")
            continue
        if not is_sha256_hex(expected_hash):
            reporter.fail(
                f"Release E2E evidence artifact hash must be lowercase SHA-256 hex: {key}"
            )
            continue
        actual_hash = release_artifact_sha256(resolved_artifact)
        if actual_hash != expected_hash:
            reporter.fail(f"Release E2E evidence artifact hash mismatch: {key}")
            continue
        reporter.ok(f"Release E2E evidence artifact exists: {key}")

    scenarios = require_non_empty_mapping(reporter, data, "scenarios", "scenario results")
    extra_scenarios = sorted(set(scenarios) - set(REQUIRED_E2E_SCENARIOS))
    for key in extra_scenarios:
        reporter.fail(f"Release E2E evidence includes unknown scenario: {key}")
    passed_evidence_notes: dict[str, list[str]] = {}
    passed_observation_references: dict[str, list[str]] = {}
    for key, label in REQUIRED_E2E_SCENARIOS.items():
        scenario = scenarios.get(key) if isinstance(scenarios, dict) else None
        if not isinstance(scenario, dict):
            reporter.fail(f"Release E2E evidence missing scenario: {key} ({label})")
            continue
        for result_key in sorted(set(scenario) - {"pass", "platforms", "evidence"}):
            reporter.fail(
                f"Release E2E evidence includes unknown scenario result key: "
                f"{key}.{result_key}"
            )
        passed = scenario.get("pass")
        platforms_value = scenario.get("platforms")
        evidence_value = scenario.get("evidence")
        expected_platforms = set(REQUIRED_E2E_SCENARIO_PLATFORMS[key])
        scenario_platforms: set[str] = set()
        if not isinstance(platforms_value, list) or not platforms_value:
            reporter.fail(f"Release E2E scenario platforms must be a non-empty list: {key}")
        else:
            invalid_platform_entries = [
                platform for platform in platforms_value if not isinstance(platform, str)
            ]
            if invalid_platform_entries:
                reporter.fail(
                    f"Release E2E scenario platforms must be strings: {key}"
                )
            normalized_platforms = [
                platform.strip() for platform in platforms_value if isinstance(platform, str)
            ]
            duplicate_platforms = sorted(
                {
                    platform
                    for platform in normalized_platforms
                    if platform and normalized_platforms.count(platform) > 1
                }
            )
            if duplicate_platforms:
                reporter.fail(
                    f"Release E2E scenario platforms include duplicates: "
                    f"{key} ({', '.join(duplicate_platforms)})"
                )
            scenario_platforms = {
                platform for platform in normalized_platforms
            }
            unknown_platforms = sorted(scenario_platforms - expected_device_platforms)
            if unknown_platforms:
                reporter.fail(
                    f"Release E2E scenario platforms include unknown platform: "
                    f"{key} ({', '.join(unknown_platforms)})"
                )
            if scenario_platforms == expected_platforms:
                reporter.ok(f"Release E2E scenario platforms match contract: {key}")
            else:
                reporter.fail(
                    f"Release E2E scenario platforms mismatch: {key} "
                    f"expected {','.join(sorted(expected_platforms))}"
                )
        if not isinstance(evidence_value, str):
            reporter.fail(f"Release E2E scenario evidence must be a string: {key}")
            continue
        evidence = evidence_value.strip()
        missing_device_ids = sorted(
            platform
            for platform in expected_platforms
            if evidence_device_ids.get(platform) and evidence_device_ids[platform] not in evidence
        )
        if (
            passed is True
            and scenario_platforms == expected_platforms
            and len(evidence) >= MIN_RELEASE_E2E_EVIDENCE_CHARS
            and not has_unresolved_evidence_placeholder(evidence)
            and has_observation_artifact_marker(evidence)
            and has_observation_artifact_reference(evidence)
            and has_scenario_observation_artifact_reference(evidence, key)
            and not missing_device_ids
        ):
            reporter.ok(f"Release E2E scenario passed: {key}")
            normalized_evidence = normalize_evidence_note(evidence)
            passed_evidence_notes.setdefault(normalized_evidence, []).append(key)
            for reference in observation_artifact_references(evidence):
                passed_observation_references.setdefault(reference, []).append(key)
        elif passed is not True:
            reporter.fail(f"Release E2E scenario not marked pass: {key}")
        elif has_unresolved_evidence_placeholder(evidence):
            reporter.fail(f"Release E2E scenario has placeholder evidence: {key}")
        elif evidence and len(evidence) < MIN_RELEASE_E2E_EVIDENCE_CHARS:
            reporter.fail(f"Release E2E scenario evidence note is too short: {key}")
        elif not has_observation_artifact_marker(evidence):
            reporter.fail(
                f"Release E2E scenario evidence missing observation artifact marker: {key}"
            )
        elif not has_observation_artifact_reference(evidence):
            reporter.fail(
                f"Release E2E scenario evidence missing observation artifact reference: {key}"
            )
        elif not has_scenario_observation_artifact_reference(evidence, key):
            reporter.fail(
                "Release E2E scenario evidence missing scenario-specific "
                f"observation artifact reference: {key}"
            )
        elif missing_device_ids:
            reporter.fail(
                f"Release E2E scenario evidence missing device id: "
                f"{key} ({', '.join(missing_device_ids)})"
            )
        else:
            reporter.fail(f"Release E2E scenario missing evidence note: {key}")
    for scenario_keys in passed_evidence_notes.values():
        if len(scenario_keys) > 1:
            reporter.fail(
                "Release E2E scenario evidence is duplicated: "
                + ", ".join(sorted(scenario_keys))
            )
    for reference, scenario_keys in passed_observation_references.items():
        if len(scenario_keys) > 1:
            reporter.fail(
                "Release E2E scenario observation artifact reference is duplicated: "
                f"{reference} ({', '.join(sorted(scenario_keys))})"
            )


def check_strict_external(reporter: Reporter) -> None:
    require_env_value(
        reporter,
        "REQUIRE_ANDROID_RELEASE_SIGNING",
        "Android release signing gate",
        "true",
    )

    credentials = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    if credentials:
        check_service_account(Path(credentials).expanduser(), reporter)
    else:
        reporter.fail("Firebase service account: FIREBASE_CREDENTIALS_PATH is not set")

    require_env_private_key_file(reporter, "APNS_AUTH_KEY_PATH", "APNs auth key")
    require_env_value(reporter, "APNS_KEY_ID", "APNs key id", r"[A-Z0-9]{10}")
    require_env_value(reporter, "APNS_TEAM_ID", "APNs team id", r"[A-Z0-9]{10}")

    require_env_private_key_file(
        reporter, "APP_STORE_CONNECT_API_KEY_PATH", "App Store Connect API key"
    )
    require_env_value(
        reporter, "APP_STORE_CONNECT_KEY_ID", "App Store Connect key id", r"[A-Z0-9]{10}"
    )
    require_env_value(
        reporter,
        "APP_STORE_CONNECT_ISSUER_ID",
        "App Store Connect issuer id",
        APP_STORE_CONNECT_ISSUER_ID_PATTERN,
    )

    require_android_device(reporter)
    require_ios_device(reporter)
    root = Path(__file__).resolve().parents[2]
    ios_entitlements = os.environ.get("IOS_RELEASE_ENTITLEMENTS_PATH", "")
    if ios_entitlements:
        if evidence_path_stays_inside_root(root, ios_entitlements):
            check_ios_release_entitlements(
                resolve_release_evidence_path(root, ios_entitlements),
                reporter,
            )
        else:
            reporter.fail("iOS release entitlements evidence path must stay inside repo")
    else:
        reporter.fail(
            "iOS release entitlements evidence: IOS_RELEASE_ENTITLEMENTS_PATH is not set"
        )
    require_env_value(reporter, "FIREBASE_TEST_DEVICE_TOKEN", "Firebase test device token")
    evidence = os.environ.get("RELEASE_E2E_EVIDENCE_PATH", "")
    if evidence:
        if evidence_path_stays_inside_root(root, evidence):
            check_release_e2e_evidence(resolve_release_evidence_path(root, evidence), reporter, root)
        else:
            reporter.fail("Release E2E evidence path must stay inside repo")
    else:
        reporter.fail("Release E2E evidence: RELEASE_E2E_EVIDENCE_PATH is not set")


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
    check_local_stt(root, reporter)
    check_ios_project(root, reporter)
    check_android_project(root, reporter)
    check_backend_push(root, reporter)
    check_tone_release_policy(root, reporter)
    check_local_env_git_policy(root, reporter)
    check_tracked_secret_leaks(root, reporter)
    check_production_compose(root, reporter)
    check_readme_release_status(root, reporter)
    check_docs(root, reporter)
    check_owll_benchmark_doc(root, reporter)
    check_tracked_release_e2e_scaffold(root, reporter)

    if args.strict:
        check_release_doc_placeholders(root, reporter)
        check_strict_external(reporter)
    else:
        reporter.warn(
            "Strict external checks skipped; run with --strict when release secrets/devices are available"
        )

    print(f"release_readiness: {len(reporter.errors)} errors, {len(reporter.warnings)} warnings")
    return 1 if reporter.errors else 0


if __name__ == "__main__":
    sys.exit(main())
