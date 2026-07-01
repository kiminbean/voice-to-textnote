import importlib.util
import sys
import zipfile
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "client"
    / "scripts"
    / "verify_promise_radar_device_gate.py"
)
SPEC = importlib.util.spec_from_file_location("promise_radar_device_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def test_parse_android_package_info_extracts_release_install_metadata():
    info = gate.parse_android_package_info(
        """
        Package [com.voicetextnote.app] (123):
          versionName=1.0.0
          firstInstallTime=2026-07-01 15:38:52
          lastUpdateTime=2026-07-01 15:39:18
        """
    )

    assert info.package_name == "com.voicetextnote.app"
    assert info.version_name == "1.0.0"
    assert gate.parse_android_timestamp(info.last_update_time) is not None


def test_ui_dump_requires_promise_radar_and_current_tab_count():
    current_dump = 'text="약속 레이더" content-desc="약속 레이더\n탭 12개 중 4번째"'
    stale_dump = 'text="요약" content-desc="요약\n탭 11개 중 1번째"'

    assert gate.ui_dump_has_promise_radar_tab(current_dump)
    assert not gate.ui_dump_has_promise_radar_tab(stale_dump)


def test_classify_ui_dump_detects_login_screen():
    ui_state = gate.classify_ui_dump(
        'content-desc="Voice TextNote" '
        'content-desc="Google로 계속하기" '
        'content-desc="게스트로 시작 (24시간 저장)"'
    )

    assert ui_state["screen"] == "login"
    assert ui_state["markers"]["login"] is True
    assert ui_state["markers"]["promise_radar"] is False


def test_classify_ui_dump_detects_server_connection_error():
    ui_state = gate.classify_ui_dump('content-desc="서버에 연결할 수 없습니다"')

    assert ui_state["screen"] == "unknown"
    assert ui_state["markers"]["server_error"] is True


def test_parse_device_lock_state_detects_locked_screen():
    state = gate.parse_device_lock_state(
        "mWakefulness=Asleep",
        "screenState=SCREEN_STATE_OFF\nmInputRestricted=true",
    )

    assert state["wakefulness"] == "Asleep"
    assert state["screen_state"] == "SCREEN_STATE_OFF"
    assert state["locked_or_asleep"] is True


def test_apk_url_guard_accepts_staging_and_rejects_production(tmp_path):
    apk_path = tmp_path / "app-release.apk"
    with zipfile.ZipFile(apk_path, "w") as archive:
        archive.writestr(
            "lib/arm64-v8a/libapp.so",
            "http://100.69.69.119:8000/api/v1\0https://api.voicetextnote.com",
        )

    ok, failures = gate.apk_uses_required_api_url(apk_path)

    assert not ok
    assert "forbidden:https://api.voicetextnote.com" in failures


def test_device_gate_evidence_report_marks_failures(tmp_path):
    apk_path = tmp_path / "app-release.apk"
    report = gate.build_evidence_report(
        apk_path=apk_path,
        api_url="http://100.69.69.119:8000/api/v1",
        apk_url_ok=False,
        apk_failures=["missing:http://100.69.69.119:8000/api/v1"],
        device_evidence={
            "serial": "device-1",
            "promise_radar_tab_visible": True,
            "tab_count": 12,
            "failures": [],
        },
        failures=["missing:http://100.69.69.119:8000/api/v1"],
    )

    assert report["passed"] is False
    assert report["device"]["promise_radar_tab_visible"] is True
    assert report["apk_failures"] == ["missing:http://100.69.69.119:8000/api/v1"]
