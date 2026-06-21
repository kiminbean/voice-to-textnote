#!/usr/bin/env python3
"""Validate local machine prerequisites for the mobile-release runner.

Run this on the macOS machine that will be registered as the GitHub
self-hosted runner before triggering the strict release workflow.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys


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


def command_output(args: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        return 127, str(exc)
    return completed.returncode, completed.stdout


def check_command(name: str, reporter: Reporter) -> bool:
    path = shutil.which(name)
    if path:
        reporter.ok(f"Command available: {name} -> {path}")
        return True
    reporter.fail(f"Command missing: {name}")
    return False


def check_macos(system_name: str, reporter: Reporter) -> None:
    if system_name == "Darwin":
        reporter.ok("Runner OS is macOS")
    else:
        reporter.fail(f"Runner OS must be macOS, got {system_name}")


def check_flutter_doctor(output: str, reporter: Reporter) -> None:
    required = [
        "Flutter",
        "Android toolchain",
        "Android SDK version 36.0.0",
        "Xcode",
        "CocoaPods version",
    ]
    missing = [snippet for snippet in required if snippet not in output]
    if missing:
        reporter.fail("flutter doctor missing: " + ", ".join(missing))
    else:
        reporter.ok("flutter doctor includes Flutter, Android SDK 36, Xcode, CocoaPods")

    if "Doctor found issues" in output:
        reporter.warn("flutter doctor reports issues; physical devices may still be unavailable")


def check_xcodebuild_version(output: str, reporter: Reporter) -> None:
    required = ["Xcode", "Build version"]
    missing = [snippet for snippet in required if snippet not in output]
    if missing:
        reporter.fail("xcodebuild -version missing: " + ", ".join(missing))
    else:
        reporter.ok("xcodebuild reports Xcode and build version")


def check_android_device(serial: str, adb_output: str, reporter: Reporter) -> None:
    if not serial:
        reporter.fail("ANDROID_DEVICE_SERIAL is not set")
        return
    pattern = re.compile(rf"^{re.escape(serial)}\s+device\b", re.MULTILINE)
    if pattern.search(adb_output):
        reporter.ok(f"Android device is attached and authorized: {serial}")
    elif serial in adb_output:
        reporter.fail(f"Android device {serial} is visible but not in device state")
    else:
        reporter.fail(f"Android device {serial} is not visible to adb")


def check_ios_device(udid: str, devicectl_output: str, reporter: Reporter) -> None:
    if not udid:
        reporter.fail("IOS_DEVICE_UDID is not set")
        return
    matching_lines = [line for line in devicectl_output.splitlines() if udid in line]
    if any(re.search(r"\bavailable\b", line) for line in matching_lines):
        reporter.ok(f"iOS device is available to devicectl: {udid}")
    elif matching_lines:
        reporter.fail(f"iOS device {udid} is visible but not available")
    else:
        reporter.fail(f"iOS device {udid} is not visible to devicectl")


def check_runner_snapshot(
    *,
    system_name: str,
    commands: set[str],
    flutter_doctor_output: str,
    xcodebuild_output: str,
    android_serial: str,
    adb_output: str,
    ios_udid: str,
    devicectl_output: str,
    reporter: Reporter,
) -> None:
    check_macos(system_name, reporter)
    for command in ["flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"]:
        if command in commands:
            reporter.ok(f"Command available: {command}")
        else:
            reporter.fail(f"Command missing: {command}")
    check_flutter_doctor(flutter_doctor_output, reporter)
    check_xcodebuild_version(xcodebuild_output, reporter)
    check_android_device(android_serial, adb_output, reporter)
    check_ios_device(ios_udid, devicectl_output, reporter)


def fetch_and_check(reporter: Reporter) -> None:
    check_macos(platform.system(), reporter)
    for command in ["flutter", "dart", "adb", "xcrun", "xcodebuild", "pod", "java"]:
        check_command(command, reporter)

    code, output = command_output(["flutter", "doctor", "-v"])
    if code == 0 or output:
        check_flutter_doctor(output, reporter)
    else:
        reporter.fail("flutter doctor failed without output")

    _, xcodebuild_output = command_output(["xcodebuild", "-version"])
    check_xcodebuild_version(xcodebuild_output, reporter)

    _, adb_output = command_output(["adb", "devices", "-l"])
    check_android_device(os.environ.get("ANDROID_DEVICE_SERIAL", ""), adb_output, reporter)

    _, devicectl_output = command_output(["xcrun", "devicectl", "list", "devices"])
    check_ios_device(os.environ.get("IOS_DEVICE_UDID", ""), devicectl_output, reporter)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    reporter = Reporter()
    fetch_and_check(reporter)
    print(
        f"mobile_release_runner: {len(reporter.errors)} errors, {len(reporter.warnings)} warnings"
    )
    return 1 if reporter.errors else 0


if __name__ == "__main__":
    sys.exit(main())
