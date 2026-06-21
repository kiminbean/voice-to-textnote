from __future__ import annotations

from pathlib import Path


def test_verify_mobile_script_checks_native_artifact_outputs():
    script = (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_mobile.sh"
    ).read_text(encoding="utf-8")

    assert 'verify_file_artifact "build/app/outputs/flutter-apk/app-debug.apk"' in script
    assert 'verify_directory_artifact "build/ios/iphoneos/Runner.app"' in script
    assert 'verify_file_artifact "build/ios/iphoneos/Runner.app/Info.plist"' in script
    assert script.index("flutter build apk --debug") < script.index(
        'verify_file_artifact "build/app/outputs/flutter-apk/app-debug.apk"'
    )
    assert script.index("flutter build ios --debug --no-codesign") < script.index(
        'verify_directory_artifact "build/ios/iphoneos/Runner.app"'
    )


def test_verify_mobile_script_fails_on_missing_or_empty_artifacts():
    script = (
        Path(__file__).resolve().parents[2] / "client/scripts/verify_mobile.sh"
    ).read_text(encoding="utf-8")

    assert '[[ ! -s "$path" ]]' in script
    assert '[[ ! -d "$path" ]]' in script
    assert 'find "$path" -mindepth 1 -print -quit' in script
