#!/usr/bin/env python3
"""Configure GitHub settings for the mobile strict release gate.

The script creates the GitHub Environment, sets non-secret device variables
when values are provided, sets environment secrets from same-named local
environment variables, and then runs the verifier.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

ENVIRONMENT = "mobile-release"
REQUIRED_SECRETS = [
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    "APNS_AUTH_KEY_P8",
    "APNS_KEY_ID",
    "APNS_TEAM_ID",
    "APP_STORE_CONNECT_API_KEY_P8",
    "APP_STORE_CONNECT_KEY_ID",
    "APP_STORE_CONNECT_ISSUER_ID",
    "FIREBASE_TEST_DEVICE_TOKEN",
]
REQUIRED_VARIABLES = [
    "ANDROID_DEVICE_SERIAL",
    "IOS_DEVICE_UDID",
]


def run(args: list[str], *, input_text: str | None = None, dry_run: bool = False) -> None:
    if dry_run:
        redacted = ["<stdin>" if arg == input_text else arg for arg in args]
        print("DRY-RUN " + " ".join(redacted))
        return
    subprocess.run(args, input=input_text, text=True, check=True)


def create_environment(repo: str, *, dry_run: bool) -> None:
    run(
        [
            "gh",
            "api",
            "--method",
            "PUT",
            f"repos/{repo}/environments/{ENVIRONMENT}",
            "--input",
            "-",
        ],
        input_text="{}\n",
        dry_run=dry_run,
    )


def set_secret(repo: str, name: str, value: str, *, dry_run: bool) -> None:
    run(
        ["gh", "secret", "set", name, "--repo", repo, "--env", ENVIRONMENT, "--body-file", "-"],
        input_text=value,
        dry_run=dry_run,
    )


def set_variable(repo: str, name: str, value: str, *, dry_run: bool) -> None:
    run(
        ["gh", "variable", "set", name, "--repo", repo, "--env", ENVIRONMENT, "--body", value],
        dry_run=dry_run,
    )


def configure_from_environment(repo: str, *, dry_run: bool) -> list[str]:
    missing: list[str] = []
    create_environment(repo, dry_run=dry_run)

    for name in REQUIRED_VARIABLES:
        value = os.environ.get(name, "").strip()
        if value:
            set_variable(repo, name, value, dry_run=dry_run)
        else:
            missing.append(name)

    for name in REQUIRED_SECRETS:
        value = os.environ.get(name, "")
        if value:
            set_secret(repo, name, value, dry_run=dry_run)
        else:
            missing.append(name)

    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="kiminbean/voice-to-textnote")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print gh operations without writing settings.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Do not run verify_github_mobile_release_env.py after configuration.",
    )
    args = parser.parse_args()

    if shutil.which("gh") is None:
        print("FAIL GitHub CLI missing: gh", file=sys.stderr)
        return 1

    missing = configure_from_environment(args.repo, dry_run=args.dry_run)
    if missing:
        print("WARN Missing local values; not configured: " + ", ".join(missing))

    if args.skip_verify or args.dry_run:
        return 0 if not missing else 1

    script = os.path.join(os.path.dirname(__file__), "verify_github_mobile_release_env.py")
    return subprocess.run([sys.executable, script, "--repo", args.repo], check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
