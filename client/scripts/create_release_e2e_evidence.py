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
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_release_readiness import (  # noqa: E402
    CANONICAL_RELEASE_ARTIFACT_PATHS,
    REQUIRED_E2E_SCENARIO_PLATFORMS,
    REQUIRED_E2E_SCENARIOS,
    artifact_path_stays_inside_root,
    evidence_path_stays_inside_root,
    release_artifact_sha256,
    release_artifact_structure_error,
    resolve_release_artifact_path,
    resolve_release_evidence_path,
)

DEFAULT_ANDROID_APK = CANONICAL_RELEASE_ARTIFACT_PATHS["android_apk"]
DEFAULT_IOS_RUNNER_APP = CANONICAL_RELEASE_ARTIFACT_PATHS["ios_runner_app"]
RELEASE_ARTIFACT_TYPES = {
    "android_apk": "file",
    "ios_runner_app": "directory",
}


def command_output(args: list[str], *, timeout: int = 10) -> str:
    try:
        completed = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def android_device_metadata(serial: str) -> dict[str, str]:
    if not serial:
        return {"model": "", "os_version": ""}
    model = command_output(["adb", "-s", serial, "shell", "getprop", "ro.product.model"])
    version = command_output(
        ["adb", "-s", serial, "shell", "getprop", "ro.build.version.release"]
    )
    return {
        "model": model,
        "os_version": f"Android {version}" if version else "",
    }


def devicectl_devices() -> list[dict[str, object]]:
    with tempfile.NamedTemporaryFile(suffix=".json") as output_file:
        try:
            completed = subprocess.run(
                [
                    "xcrun",
                    "devicectl",
                    "list",
                    "devices",
                    "--json-output",
                    output_file.name,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
            )
            output = Path(output_file.name).read_text(encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired):
            return []
    if completed.returncode != 0:
        return []
    start = output.find('{"result"')
    if start == -1:
        start = output.find("{")
    if start == -1:
        return []
    try:
        payload = json.loads(output[start:])
    except json.JSONDecodeError:
        return []
    result = payload.get("result")
    if not isinstance(result, dict):
        return []
    devices = result.get("devices")
    return devices if isinstance(devices, list) else []


def ios_device_metadata(udid: str) -> dict[str, str]:
    if not udid:
        return {"model": "", "os_version": ""}
    for device in devicectl_devices():
        if not isinstance(device, dict):
            continue
        hardware = device.get("hardwareProperties")
        properties = device.get("deviceProperties")
        connection = device.get("connectionProperties")
        if not isinstance(hardware, dict) or not isinstance(properties, dict):
            continue
        hostnames = connection.get("potentialHostnames") if isinstance(connection, dict) else None
        candidates = [
            device.get("identifier"),
            hardware.get("udid"),
        ]
        if isinstance(hostnames, list):
            candidates.extend(hostnames)
        if not any(isinstance(value, str) and udid in value for value in candidates):
            continue
        model = hardware.get("marketingName") or hardware.get("productType") or ""
        version = properties.get("osVersionNumber") or ""
        return {
            "model": str(model),
            "os_version": f"iOS {version}" if version else "",
        }
    return {"model": "", "os_version": ""}


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


def validate_release_artifacts(root: Path, artifacts: dict[str, str]) -> None:
    for key, artifact_path in artifacts.items():
        if not artifact_path_stays_inside_root(root, artifact_path):
            raise ValueError(f"release artifact path must stay inside repo: {key}")
        resolved = resolve_release_artifact_path(root, artifact_path)
        expected_type = RELEASE_ARTIFACT_TYPES[key]
        if expected_type == "file" and not resolved.is_file():
            raise ValueError(f"missing release artifact file: {key} ({resolved})")
        if expected_type == "directory" and not resolved.is_dir():
            raise ValueError(f"missing release artifact directory: {key} ({resolved})")
        structure_error = release_artifact_structure_error(root, key, artifact_path)
        if structure_error:
            raise ValueError(f"release {structure_error}")


def build_evidence(root: Path, *, android_apk: str, ios_runner_app: str) -> dict[str, object]:
    revision = git_revision(root)
    artifacts = {
        "android_apk": android_apk,
        "ios_runner_app": ios_runner_app,
    }
    validate_release_artifacts(root, artifacts)
    ios_entitlements = os.environ.get("IOS_RELEASE_ENTITLEMENTS_PATH", "")
    ios_entitlements_hash = ""
    if ios_entitlements and not evidence_path_stays_inside_root(root, ios_entitlements):
        raise ValueError("iOS entitlements evidence path must stay inside repo")
    if ios_entitlements:
        ios_entitlements_path = resolve_release_evidence_path(root, ios_entitlements)
        if not ios_entitlements_path.is_file():
            raise ValueError("iOS entitlements evidence file is missing")
        ios_entitlements_hash = release_artifact_sha256(ios_entitlements_path)
    android_serial = os.environ.get("ANDROID_DEVICE_SERIAL", "")
    ios_udid = os.environ.get("IOS_DEVICE_UDID", "")
    android_metadata = android_device_metadata(android_serial)
    ios_metadata = ios_device_metadata(ios_udid)
    return {
        "tested_at": datetime.now(UTC).isoformat(),
        "tester": os.environ.get("USER", "release-operator"),
        "backend_version": revision,
        "client_version": revision,
        "release_gate": {
            "android_release_signing": os.environ.get("REQUIRE_ANDROID_RELEASE_SIGNING")
            == "true",
            "ios_production_entitlements": bool(ios_entitlements_hash),
            "ios_entitlements_sha256": ios_entitlements_hash,
        },
        "devices": {
            "android": {
                "serial": android_serial,
                "model": android_metadata["model"],
                "os_version": android_metadata["os_version"],
            },
            "ios": {
                "udid": ios_udid,
                "model": ios_metadata["model"],
                "os_version": ios_metadata["os_version"],
            },
        },
        "artifacts": artifacts,
        "artifact_sha256": {
            key: release_artifact_sha256(resolve_release_artifact_path(root, artifact_path))
            for key, artifact_path in artifacts.items()
        },
        "scenarios": {
            key: {
                "pass": False,
                "platforms": list(REQUIRED_E2E_SCENARIO_PLATFORMS[key]),
                "evidence": f"TODO: {label}",
            }
            for key, label in REQUIRED_E2E_SCENARIOS.items()
        },
    }


def resolve_output_path(root: Path, output_path: str) -> Path:
    if not evidence_path_stays_inside_root(root, output_path):
        raise ValueError("release evidence output path must stay inside repo")
    return resolve_release_evidence_path(root, output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Path to write release evidence JSON.")
    parser.add_argument("--android-apk", default=DEFAULT_ANDROID_APK)
    parser.add_argument("--ios-runner-app", default=DEFAULT_IOS_RUNNER_APP)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    try:
        output_path = resolve_output_path(root, args.output)
    except ValueError as exc:
        print(f"Cannot create release E2E evidence scaffold: {exc}", file=sys.stderr)
        return 1
    if output_path.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {output_path}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence = build_evidence(
            root,
            android_apk=args.android_apk,
            ios_runner_app=args.ios_runner_app,
        )
    except ValueError as exc:
        print(f"Cannot create release E2E evidence scaffold: {exc}", file=sys.stderr)
        return 1
    output_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote release E2E evidence scaffold: {output_path}")
    print("Edit every scenario to pass=true with real evidence before strict readiness.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
