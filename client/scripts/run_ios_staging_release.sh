#!/bin/bash
set -euo pipefail

# iPhone 실기기 private staging 릴리스 설치 전용 스크립트.
# 기본 release 환경은 production placeholder이므로 직접 flutter run --release를 사용하지 않는다.

DEVICE_ID="${IOS_DEVICE_UDID:-00008150-000239020C08401C}"
API_BASE_URL="${API_BASE_URL:-http://100.69.69.119:8000/api/v1}"
API_KEYS_FIRST="${API_KEYS:-}"
API_KEY="${API_KEY:-${API_KEYS_FIRST%%,*}}"

flutter run --release --no-pub --no-resident \
  -d "$DEVICE_ID" \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=API_KEY="$API_KEY"
