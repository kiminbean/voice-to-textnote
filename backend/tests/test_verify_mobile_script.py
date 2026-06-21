from __future__ import annotations

import importlib.util
import re
from pathlib import Path


def load_create_evidence_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "client/scripts/create_release_e2e_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("create_release_e2e_evidence", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_verify_mobile_script() -> str:
    return (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_mobile.sh"
    ).read_text(encoding="utf-8")


def shell_constant(script: str, name: str) -> str:
    match = re.search(rf'^{name}="([^"]+)"$', script, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_verify_mobile_script_checks_native_artifact_outputs():
    script = read_verify_mobile_script()

    assert 'verify_file_artifact "$ANDROID_RELEASE_APK"' in script
    assert 'verify_directory_artifact "$IOS_RUNNER_APP"' in script
    assert 'verify_file_artifact "$IOS_INFO_PLIST"' in script
    assert script.index("flutter build apk --release") < script.index(
        'verify_file_artifact "$ANDROID_RELEASE_APK"'
    )
    assert script.index("flutter build ios --debug --no-codesign") < script.index(
        'verify_directory_artifact "$IOS_RUNNER_APP"'
    )


def test_verify_mobile_script_fails_on_missing_or_empty_artifacts():
    script = read_verify_mobile_script()

    assert '[[ ! -s "$path" ]]' in script
    assert '[[ ! -d "$path" ]]' in script
    assert 'find "$path" -mindepth 1 -print -quit' in script


def test_verify_mobile_script_artifact_paths_match_release_evidence_defaults():
    create = load_create_evidence_module()
    script = read_verify_mobile_script()

    assert create.DEFAULT_ANDROID_APK == f"client/{shell_constant(script, 'ANDROID_RELEASE_APK')}"
    assert create.DEFAULT_IOS_RUNNER_APP == f"client/{shell_constant(script, 'IOS_RUNNER_APP')}"
    assert shell_constant(script, "IOS_INFO_PLIST") == "$IOS_RUNNER_APP/Info.plist"
