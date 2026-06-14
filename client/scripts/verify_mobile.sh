#!/bin/bash
set -euo pipefail

run_native=false
if [[ "${1:-}" == "--native" ]]; then
  run_native=true
elif [[ "${1:-}" != "" ]]; then
  echo "Usage: $0 [--native]" >&2
  exit 2
fi

if [[ "$run_native" == true ]]; then
  android_sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  if [[ -z "$android_sdk" || ! -d "$android_sdk" ]]; then
    echo "Android SDK not found. Set ANDROID_HOME or ANDROID_SDK_ROOT to run native Android verification." >&2
    exit 1
  fi
fi

flutter pub get
flutter analyze
flutter test
dart --disable-analytics run tool/local_stt_smoke.dart

if [[ "$run_native" != true ]]; then
  echo "Skipping native Android/iOS builds. Run '$0 --native' on a machine with Android SDK and Xcode/CocoaPods access."
  exit 0
fi

flutter build apk --debug

if [[ "$(uname -s)" == "Darwin" ]]; then
  flutter build ios --debug --no-codesign
fi
