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

find_android_build_tool() {
  local tool="$1"

  if command -v "$tool" >/dev/null 2>&1; then
    command -v "$tool"
    return 0
  fi

  local android_sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ -n "$android_sdk" && -d "$android_sdk/build-tools" ]]; then
    local candidate
    candidate="$(find "$android_sdk/build-tools" -type f -name "$tool" | sort -V | tail -n 1)"
    if [[ -n "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  fi

  return 1
}

verify_signed_android_artifact() {
  local path="$1"

  if [[ "${REQUIRE_ANDROID_RELEASE_SIGNING:-false}" != "true" ]]; then
    echo "Skipping Android release signing verification. Set REQUIRE_ANDROID_RELEASE_SIGNING=true for strict release."
    return 0
  fi

  local apksigner
  if ! apksigner="$(find_android_build_tool apksigner)"; then
    echo "apksigner not found. Install Android SDK build-tools or add apksigner to PATH." >&2
    exit 1
  fi

  local verify_output
  verify_output="$(mktemp)"
  if ! "$apksigner" verify --print-certs "$path" >"$verify_output" 2>&1; then
    cat "$verify_output" >&2
    rm -f "$verify_output"
    exit 1
  fi
  cat "$verify_output"
  rm -f "$verify_output"
  echo "Verified signed Android release APK: $path"
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
verify_signed_android_artifact "$ANDROID_RELEASE_APK"

if [[ "$(uname -s)" == "Darwin" ]]; then
  flutter build ios --debug --no-codesign
  verify_directory_artifact "$IOS_RUNNER_APP" "iOS no-codesign app"
  verify_file_artifact "$IOS_INFO_PLIST" "iOS Info.plist"
fi
