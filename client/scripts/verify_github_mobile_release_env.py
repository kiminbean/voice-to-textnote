#!/usr/bin/env python3
"""Validate GitHub settings needed to run mobile strict release evidence.

This does not inspect secret values. It checks that the repository has the
required environment, secret names, variable names, and a self-hosted runner
with the labels needed by .github/workflows/mobile.yml.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any

ENVIRONMENT = "mobile-release"
REQUIRED_RUNNER_LABELS = {"self-hosted", "macOS", "mobile-release"}
REQUIRED_SECRETS = {
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    "APNS_AUTH_KEY_P8",
    "APNS_KEY_ID",
    "APNS_TEAM_ID",
    "APP_STORE_CONNECT_API_KEY_P8",
    "APP_STORE_CONNECT_KEY_ID",
    "APP_STORE_CONNECT_ISSUER_ID",
    "FIREBASE_TEST_DEVICE_TOKEN",
}
REQUIRED_VARIABLES = {
    "ANDROID_DEVICE_SERIAL",
    "IOS_DEVICE_UDID",
}


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def ok(self, message: str) -> None:
        print(f"PASS {message}")

    def fail(self, message: str) -> None:
        self.errors.append(message)
        print(f"FAIL {message}")


def run_json(args: list[str]) -> Any:
    output = subprocess.check_output(args, text=True, stderr=subprocess.PIPE)
    return json.loads(output)


def run_name_list(args: list[str]) -> set[str]:
    output = subprocess.check_output(args, text=True, stderr=subprocess.PIPE)
    data = json.loads(output)
    return {item["name"] for item in data if item.get("name")}


def runner_has_required_labels(runner: dict[str, Any]) -> bool:
    labels = {
        label.get("name")
        for label in runner.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    }
    return REQUIRED_RUNNER_LABELS.issubset(labels)


def runner_is_online_release_runner(runner: dict[str, Any]) -> bool:
    return runner_has_required_labels(runner) and runner.get("status") == "online"


def check_snapshot(
    *,
    environments: set[str],
    runners: list[dict[str, Any]],
    secrets: set[str],
    variables: set[str],
    reporter: Reporter,
) -> None:
    if ENVIRONMENT in environments:
        reporter.ok(f"GitHub Environment exists: {ENVIRONMENT}")
    else:
        reporter.fail(f"GitHub Environment missing: {ENVIRONMENT}")

    if any(runner_is_online_release_runner(runner) for runner in runners):
        reporter.ok(
            "Online self-hosted runner has labels: " + ", ".join(sorted(REQUIRED_RUNNER_LABELS))
        )
    else:
        reporter.fail(
            "No online self-hosted runner has required labels: "
            + ", ".join(sorted(REQUIRED_RUNNER_LABELS))
        )

    missing_secrets = sorted(REQUIRED_SECRETS - secrets)
    if missing_secrets:
        reporter.fail("GitHub Environment secrets missing: " + ", ".join(missing_secrets))
    else:
        reporter.ok("GitHub Environment secrets are configured")

    missing_variables = sorted(REQUIRED_VARIABLES - variables)
    if missing_variables:
        reporter.fail("GitHub Environment variables missing: " + ", ".join(missing_variables))
    else:
        reporter.ok("GitHub Environment variables are configured")


def fetch_and_check(repo: str, reporter: Reporter) -> None:
    if shutil.which("gh") is None:
        reporter.fail("GitHub CLI missing: gh")
        return

    environments_payload = run_json(["gh", "api", f"repos/{repo}/environments", "--jq", "."])
    environments = {
        item["name"] for item in environments_payload.get("environments", []) if item.get("name")
    }

    runners_payload = run_json(["gh", "api", f"repos/{repo}/actions/runners", "--jq", "."])
    runners = runners_payload.get("runners", [])

    try:
        secrets = run_name_list(
            [
                "gh",
                "secret",
                "list",
                "--repo",
                repo,
                "--env",
                ENVIRONMENT,
                "--json",
                "name",
            ]
        )
    except subprocess.CalledProcessError:
        secrets = set()

    try:
        variables = run_name_list(
            [
                "gh",
                "variable",
                "list",
                "--repo",
                repo,
                "--env",
                ENVIRONMENT,
                "--json",
                "name",
            ]
        )
    except subprocess.CalledProcessError:
        variables = set()

    check_snapshot(
        environments=environments,
        runners=runners,
        secrets=secrets,
        variables=variables,
        reporter=reporter,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="kiminbean/voice-to-textnote")
    args = parser.parse_args()

    reporter = Reporter()
    fetch_and_check(args.repo, reporter)
    print(f"github_mobile_release_env: {len(reporter.errors)} errors")
    return 1 if reporter.errors else 0


if __name__ == "__main__":
    sys.exit(main())
