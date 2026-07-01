#!/usr/bin/env python3
"""Verify Android Promise Radar release-gate evidence on a connected device."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PACKAGE = "com.voicetextnote.app"
DEFAULT_API_URL = "http://100.69.69.119:8000/api/v1"
DEFAULT_APK = "client/build/app/outputs/flutter-apk/app-release.apk"


@dataclass(frozen=True)
class AndroidPackageInfo:
    package_name: str | None
    version_name: str | None
    first_install_time: str | None
    last_update_time: str | None


def parse_android_package_info(output: str) -> AndroidPackageInfo:
    """Extract install metadata from `adb shell dumpsys package` output."""

    def match(pattern: str) -> str | None:
        found = re.search(pattern, output)
        return found.group(1).strip() if found else None

    return AndroidPackageInfo(
        package_name=match(r"Package \[([^\]]+)\]"),
        version_name=match(r"versionName=([^\s]+)"),
        first_install_time=match(r"firstInstallTime=([^\n]+)"),
        last_update_time=match(r"lastUpdateTime=([^\n]+)"),
    )


def parse_android_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def ui_dump_tab_count(ui_dump: str) -> int | None:
    found = re.search(r"탭\s+(\d+)개", ui_dump)
    return int(found.group(1)) if found else None


def ui_dump_has_promise_radar_tab(ui_dump: str, *, expected_tab_count: int = 12) -> bool:
    return "약속 레이더" in ui_dump and ui_dump_tab_count(ui_dump) == expected_tab_count


def classify_ui_dump(ui_dump: str) -> dict:
    markers = {
        "login": (
            "Google로 계속하기" in ui_dump
            and "게스트로 시작" in ui_dump
            and "Voice TextNote" in ui_dump
        ),
        "promise_radar": "약속 레이더" in ui_dump,
        "home": "새 녹음" in ui_dump or "회의 목록" in ui_dump,
        "server_error": "서버에 연결할 수 없습니다" in ui_dump,
    }
    if markers["promise_radar"]:
        screen = "promise_radar_result"
    elif markers["login"]:
        screen = "login"
    elif markers["home"]:
        screen = "home"
    else:
        screen = "unknown"
    return {
        "screen": screen,
        "markers": markers,
    }


def apk_text_blob(apk_path: Path) -> str:
    with zipfile.ZipFile(apk_path) as archive:
        parts: list[str] = []
        for name in archive.namelist():
            if name.endswith((".so", ".txt", ".json", ".xml", ".plist")) or "libapp.so" in name:
                parts.append(archive.read(name).decode("latin-1", errors="ignore"))
        return "\n".join(parts)


def apk_uses_required_api_url(
    apk_path: Path,
    *,
    required_api_url: str = DEFAULT_API_URL,
    forbidden_fragments: tuple[str, ...] = ("https://api.voicetextnote.com",),
) -> tuple[bool, list[str]]:
    blob = apk_text_blob(apk_path)
    missing_or_forbidden: list[str] = []
    if required_api_url not in blob:
        missing_or_forbidden.append(f"missing:{required_api_url}")
    for fragment in forbidden_fragments:
        if fragment in blob:
            missing_or_forbidden.append(f"forbidden:{fragment}")
    return not missing_or_forbidden, missing_or_forbidden


def run_adb(args: list[str], *, serial: str | None = None) -> str:
    command = ["adb"]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return completed.stdout


def collect_ui_dump(*, serial: str | None = None) -> str:
    remote_path = "/sdcard/promise_radar_gate.xml"
    run_adb(["shell", "uiautomator", "dump", remote_path], serial=serial)
    return run_adb(["shell", "cat", remote_path], serial=serial)


def parse_device_lock_state(power_output: str, policy_output: str) -> dict:
    wakefulness = None
    found_wakefulness = re.search(r"mWakefulness=([A-Za-z]+)", power_output)
    if found_wakefulness:
        wakefulness = found_wakefulness.group(1)
    screen_state = None
    found_screen = re.search(r"screenState=([A-Z_]+)", policy_output)
    if found_screen:
        screen_state = found_screen.group(1)
    input_restricted = "mInputRestricted=true" in policy_output
    return {
        "wakefulness": wakefulness,
        "screen_state": screen_state,
        "input_restricted": input_restricted,
        "locked_or_asleep": wakefulness != "Awake"
        or screen_state == "SCREEN_STATE_OFF"
        or input_restricted,
    }


def collect_device_evidence(
    *,
    package_name: str,
    serial: str | None,
    expected_tab_count: int,
) -> dict:
    package_output = run_adb(["shell", "dumpsys", "package", package_name], serial=serial)
    package_info = parse_android_package_info(package_output)
    lock_state = parse_device_lock_state(
        run_adb(["shell", "dumpsys", "power"], serial=serial),
        run_adb(["shell", "dumpsys", "window", "policy"], serial=serial),
    )
    ui_dump = collect_ui_dump(serial=serial)
    ui_state = classify_ui_dump(ui_dump)
    tab_count = ui_dump_tab_count(ui_dump)
    has_promise_radar_tab = ui_dump_has_promise_radar_tab(
        ui_dump,
        expected_tab_count=expected_tab_count,
    )
    failures: list[str] = []
    if package_info.package_name != package_name:
        failures.append(f"installed package mismatch: {package_info.package_name}")
    if parse_android_timestamp(package_info.last_update_time) is None:
        failures.append("lastUpdateTime missing or unparsable")
    if lock_state["locked_or_asleep"]:
        failures.append(
            "device screen is locked or asleep; unlock and keep the app visible before UI gate"
        )
    if ui_state["screen"] == "login":
        failures.append(
            "app is on login screen; sign in or start guest and open a result screen before UI gate"
        )
    if ui_state["markers"]["server_error"]:
        failures.append("app is showing server connection error")
    if not has_promise_radar_tab:
        failures.append(f"Promise Radar tab missing or stale tab count: {tab_count}")
    return {
        "serial": serial,
        "package_name": package_info.package_name,
        "version_name": package_info.version_name,
        "first_install_time": package_info.first_install_time,
        "last_update_time": package_info.last_update_time,
        "promise_radar_tab_visible": has_promise_radar_tab,
        "tab_count": tab_count,
        "expected_tab_count": expected_tab_count,
        "lock_state": lock_state,
        "ui_state": ui_state,
        "failures": failures,
    }


def verify_device(
    *,
    package_name: str,
    serial: str | None,
    expected_tab_count: int,
) -> list[str]:
    return collect_device_evidence(
        package_name=package_name,
        serial=serial,
        expected_tab_count=expected_tab_count,
    )["failures"]


def build_evidence_report(
    *,
    apk_path: Path,
    api_url: str,
    apk_url_ok: bool,
    apk_failures: list[str],
    device_evidence: dict | None,
    failures: list[str],
) -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "apk_path": str(apk_path),
        "required_api_url": api_url,
        "apk_url_ok": apk_url_ok,
        "apk_failures": apk_failures,
        "device": device_evidence,
        "passed": not failures,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=None, help="ADB device serial")
    parser.add_argument("--package", default=DEFAULT_PACKAGE, help="Android package name")
    parser.add_argument("--apk", default=DEFAULT_APK, help="Release APK path to inspect")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Required staging API URL")
    parser.add_argument("--expected-tab-count", type=int, default=12)
    parser.add_argument("--skip-device", action="store_true", help="Only verify APK contents")
    parser.add_argument("--evidence-out", default=None, help="Write JSON evidence to this path")
    args = parser.parse_args(argv)

    failures: list[str] = []
    apk_url_ok = False
    apk_failures: list[str] = []
    device_evidence: dict | None = None
    apk_path = Path(args.apk)
    if not apk_path.exists():
        failures.append(f"APK missing: {apk_path}")
    else:
        apk_url_ok, apk_failures = apk_uses_required_api_url(
            apk_path,
            required_api_url=args.api_url,
        )
        if not apk_url_ok:
            failures.extend(apk_failures)

    if not args.skip_device:
        try:
            device_evidence = collect_device_evidence(
                package_name=args.package,
                serial=args.serial,
                expected_tab_count=args.expected_tab_count,
            )
            failures.extend(device_evidence["failures"])
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            failures.append(f"ADB verification failed: {exc}")

    if args.evidence_out:
        report = build_evidence_report(
            apk_path=apk_path,
            api_url=args.api_url,
            apk_url_ok=apk_url_ok,
            apk_failures=apk_failures,
            device_evidence=device_evidence,
            failures=failures,
        )
        evidence_path = Path(args.evidence_out)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS Promise Radar Android device gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
