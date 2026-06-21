#!/bin/bash
set -euo pipefail

run_native=false
if [[ "${1:-}" == "--native" ]]; then
  run_native=true
elif [[ "${1:-}" != "" ]]; then
  echo "Usage: $0 [--native]" >&2
  exit 2
fi

ANDROID_RELEASE_APK="build/app/outputs/flutter-apk/app-release.apk"
IOS_RUNNER_APP="build/ios/iphoneos/Runner.app"
IOS_INFO_PLIST="$IOS_RUNNER_APP/Info.plist"

if [[ "$run_native" == true ]]; then
  android_sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ -z "$android_sdk" || ! -d "$android_sdk" ]]; then
    echo "Android SDK not found. Set ANDROID_HOME or ANDROID_SDK_ROOT to run native Android verification." >&2
    exit 1
  fi
fi

verify_file_artifact() {
  local path="$1"
  local label="$2"
  if [[ ! -s "$path" ]]; then
    echo "$label artifact missing or empty: $path" >&2
    exit 1
  fi
  echo "Verified $label artifact: $path"
}

verify_directory_artifact() {
  local path="$1"
  local label="$2"
  if [[ ! -d "$path" ]]; then
    echo "$label artifact directory missing: $path" >&2
    exit 1
  fi
  if [[ -z "$(find "$path" -mindepth 1 -print -quit)" ]]; then
    echo "$label artifact directory empty: $path" >&2
    exit 1
  fi
  echo "Verified $label artifact directory: $path"
}

flutter pub get
flutter analyze
flutter test
dart --disable-analytics run tool/local_stt_smoke.dart

if [[ "$run_native" != true ]]; then
  echo "Skipping native Android/iOS builds. Run '$0 --native' on a machine with Android SDK and Xcode/CocoaPods access."
  exit 0
fi

flutter build apk --release
verify_file_artifact "$ANDROID_RELEASE_APK" "Android release APK"

if [[ "$(uname -s)" == "Darwin" ]]; then
  flutter build ios --debug --no-codesign
  verify_directory_artifact "$IOS_RUNNER_APP" "iOS no-codesign app"
  verify_file_artifact "$IOS_INFO_PLIST" "iOS Info.plist"
fi
