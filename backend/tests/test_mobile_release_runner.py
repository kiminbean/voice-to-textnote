from __future__ import annotations

import importlib.util
from pathlib import Path


def load_runner_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_mobile_release_runner.py"
    )
    spec = importlib.util.spec_from_file_location("verify_mobile_release_runner", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def complete_doctor_output() -> str:
    return "\n".join(
        [
            "[✓] Flutter",
            "[✓] Android toolchain - develop for Android devices (Android SDK version 36.0.0)",
            "[✓] Xcode - develop for iOS and macOS",
            "CocoaPods version 1.16.2",
        ]
    )


def complete_xcodebuild_output() -> str:
    return "\n".join(["Xcode 16.4", "Build version 16F6"])


def test_mobile_release_runner_accepts_complete_snapshot():
    module = load_runner_module()
    reporter = module.Reporter()

    module.check_runner_snapshot(
        system_name="Darwin",
        commands={"flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"},
        flutter_doctor_output=complete_doctor_output(),
        xcodebuild_output=complete_xcodebuild_output(),
        android_serial="android-serial",
        adb_output="List of devices attached\nandroid-serial device product:pixel\n",
        ios_udid="ios-udid",
        devicectl_output="iPhone ios-udid available iPhone17,1",
        reporter=reporter,
    )

    assert reporter.errors == []


def test_mobile_release_runner_rejects_unavailable_ios_device():
    module = load_runner_module()
    reporter = module.Reporter()

    module.check_runner_snapshot(
        system_name="Darwin",
        commands={"flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"},
        flutter_doctor_output=complete_doctor_output(),
        xcodebuild_output=complete_xcodebuild_output(),
        android_serial="android-serial",
        adb_output="List of devices attached\nandroid-serial device product:pixel\n",
        ios_udid="ios-udid",
        devicectl_output="iPhone ios-udid unavailable iPhone17,1",
        reporter=reporter,
    )

    assert any("visible but not available" in error for error in reporter.errors)


def test_mobile_release_runner_rejects_missing_android_device():
    module = load_runner_module()
    reporter = module.Reporter()

    module.check_runner_snapshot(
        system_name="Darwin",
        commands={"flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"},
        flutter_doctor_output=complete_doctor_output(),
        xcodebuild_output=complete_xcodebuild_output(),
        android_serial="android-serial",
        adb_output="List of devices attached\n",
        ios_udid="ios-udid",
        devicectl_output="iPhone ios-udid available iPhone17,1",
        reporter=reporter,
    )

    assert any("not visible to adb" in error for error in reporter.errors)


def test_mobile_release_runner_rejects_broken_xcodebuild():
    module = load_runner_module()
    reporter = module.Reporter()

    module.check_runner_snapshot(
        system_name="Darwin",
        commands={"flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"},
        flutter_doctor_output=complete_doctor_output(),
        xcodebuild_output="xcode-select: error: tool 'xcodebuild' requires Xcode",
        android_serial="android-serial",
        adb_output="List of devices attached\nandroid-serial device product:pixel\n",
        ios_udid="ios-udid",
        devicectl_output="iPhone ios-udid available iPhone17,1",
        reporter=reporter,
    )

    assert any("xcodebuild -version missing" in error for error in reporter.errors)
