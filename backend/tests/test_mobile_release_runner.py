from __future__ import annotations

import importlib.util
import json
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


def devicectl_output_with_hardware_udid(
    *,
    core_device_id: str = "core-device-id",
    hardware_udid: str = "ios-udid",
    state: str = "available",
) -> str:
    table = f"iPhone example.local {core_device_id} {state} iPhone17,1"
    payload = {
        "result": {
            "devices": [
                {
                    "identifier": core_device_id,
                    "hardwareProperties": {"udid": hardware_udid},
                    "connectionProperties": {
                        "potentialHostnames": [
                            f"{core_device_id}.coredevice.local",
                            f"{hardware_udid}.coredevice.local",
                        ]
                    },
                }
            ]
        }
    }
    return table + "\n" + json.dumps(payload)


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


def test_mobile_release_runner_accepts_hardware_udid_from_devicectl_json():
    module = load_runner_module()
    reporter = module.Reporter()

    module.check_runner_snapshot(
        system_name="Darwin",
        commands={"flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"},
        flutter_doctor_output=complete_doctor_output(),
        xcodebuild_output=complete_xcodebuild_output(),
        android_serial="android-serial",
        adb_output="List of devices attached\nandroid-serial device product:pixel\n",
        ios_udid="00008150-000239020C08401C",
        devicectl_output=devicectl_output_with_hardware_udid(
            core_device_id="C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA",
            hardware_udid="00008150-000239020C08401C",
        ),
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
        devicectl_output=devicectl_output_with_hardware_udid(state="unavailable"),
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
