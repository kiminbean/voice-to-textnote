#!/usr/bin/env python3
"""Create a release E2E evidence JSON scaffold.

The output is intentionally not marked as passing. Operators must edit each
scenario with real physical-device observations before running strict release
readiness.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_release_readiness import REQUIRED_E2E_SCENARIOS  # noqa: E402, I001


DEFAULT_ANDROID_APK = "client/build/app/outputs/flutter-apk/app-debug.apk"
DEFAULT_IOS_RUNNER_APP = "client/build/ios/iphoneos/Runner.app"


def git_revision(root: Path) -> str:
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


def build_evidence(root: Path, *, android_apk: str, ios_runner_app: str) -> dict[str, object]:
    revision = git_revision(root)
    return {
        "tested_at": datetime.now(UTC).isoformat(),
        "tester": os.environ.get("USER", "release-operator"),
        "backend_version": revision,
        "client_version": revision,
        "devices": {
            "android": {
                "serial": os.environ.get("ANDROID_DEVICE_SERIAL", ""),
                "model": "",
                "os_version": "",
            },
            "ios": {
                "udid": os.environ.get("IOS_DEVICE_UDID", ""),
                "model": "",
                "os_version": "",
            },
        },
        "artifacts": {
            "android_apk": android_apk,
            "ios_runner_app": ios_runner_app,
        },
        "scenarios": {
            key: {
                "pass": False,
                "evidence": f"TODO: {label}",
            }
            for key, label in REQUIRED_E2E_SCENARIOS.items()
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Path to write release evidence JSON.")
    parser.add_argument("--android-apk", default=DEFAULT_ANDROID_APK)
    parser.add_argument("--ios-runner-app", default=DEFAULT_IOS_RUNNER_APP)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    output_path = Path(args.output).expanduser()
    if output_path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {output_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence(
        root,
        android_apk=args.android_apk,
        ios_runner_app=args.ios_runner_app,
    )
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote release E2E evidence scaffold: {output_path}")
    print("Edit every scenario to pass=true with real evidence before strict readiness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
