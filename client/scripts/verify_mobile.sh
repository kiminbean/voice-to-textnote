#!/bin/bash
set -euo pipefail

flutter pub get
flutter analyze
flutter test
flutter build apk --debug

if [[ "$(uname -s)" == "Darwin" ]]; then
  flutter build ios --debug --no-codesign
fi
