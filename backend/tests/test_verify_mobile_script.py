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


def read_run_production_script() -> str:
    return (
        Path(__file__).resolve().parents[2] / "client/scripts/run_production.sh"
    ).read_text(encoding="utf-8")


def shell_constant(script: str, name: str) -> str:
    match = re.search(rf'^{name}="([^"]+)"$', script, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_verify_mobile_script_checks_native_artifact_outputs():
    script = read_verify_mobile_script()

    assert 'verify_file_artifact "$ANDROID_RELEASE_APK"' in script
    assert 'verify_signed_android_artifact "$ANDROID_RELEASE_APK"' in script
    assert 'verify_directory_artifact "$IOS_RUNNER_APP"' in script
    assert 'verify_file_artifact "$IOS_INFO_PLIST"' in script
    assert 'APP_ENV="${APP_ENV:-staging}"' in script
    assert 'API_BASE_URL="${API_BASE_URL:-http://100.69.69.119:8000/api/v1}"' in script
    assert 'API_KEY="${API_KEY:-${API_KEYS_FIRST%%,*}}"' in script
    assert '"--dart-define=ENV=$APP_ENV"' in script
    assert '"--dart-define=API_BASE_URL=$API_BASE_URL"' in script
    assert '"--dart-define=API_KEY=$API_KEY"' in script
    assert script.index("flutter build apk --release") < script.index(
        'verify_file_artifact "$ANDROID_RELEASE_APK"'
    )
    assert script.index('verify_file_artifact "$ANDROID_RELEASE_APK"') < script.index(
        'verify_signed_android_artifact "$ANDROID_RELEASE_APK"'
    )
    assert script.index("flutter build ios --release --no-codesign") < script.index(
        'verify_directory_artifact "$IOS_RUNNER_APP"'
    )


def test_verify_mobile_script_fails_on_missing_or_empty_artifacts():
    script = read_verify_mobile_script()

    assert '[[ ! -s "$path" ]]' in script
    assert '[[ ! -d "$path" ]]' in script
    assert 'find "$path" -mindepth 1 -print -quit' in script


def test_verify_mobile_script_rejects_android_debug_certificate():
    script = read_verify_mobile_script()

    assert "CN=Android Debug" in script
    assert "Android release APK is signed with the Android debug certificate" in script
    assert 'grep -Eiq' in script


def test_verify_mobile_script_artifact_paths_match_release_evidence_defaults():
    create = load_create_evidence_module()
    script = read_verify_mobile_script()

    assert create.DEFAULT_ANDROID_APK == f"client/{shell_constant(script, 'ANDROID_RELEASE_APK')}"
    assert create.DEFAULT_IOS_RUNNER_APP == f"client/{shell_constant(script, 'IOS_RUNNER_APP')}"
    assert shell_constant(script, "IOS_INFO_PLIST") == "$IOS_RUNNER_APP/Info.plist"


def test_run_production_script_requires_https_and_health_check():
    script = read_run_production_script()

    assert 'API_BASE_URL="${API_BASE_URL:?API_BASE_URL 환경 변수를 실제 운영 HTTPS URL로 설정하세요}"' in script
    assert 'API_HEALTH_URL="${API_HEALTH_URL:-${API_BASE_URL%/}/health}"' in script
    assert 'if [[ "$API_BASE_URL" != https://* ]]; then' in script
    assert 'curl --fail --silent --show-error --max-time "$API_HEALTH_TIMEOUT" "$API_HEALTH_URL"' in script
    assert "프로덕션 API health check 실패" in script
    assert script.index('curl --fail --silent --show-error') < script.index(
        "flutter run --release"
    )
