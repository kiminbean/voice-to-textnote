#!/bin/bash
# 스테이징 환경 실행 스크립트 (Tailscale IP)
# Android/iOS 실기기 검증 시 ENV와 API_BASE_URL을 함께 고정한다.
# 기본 release 환경은 production placeholder를 사용하므로 API_BASE_URL 누락 금지.
set -euo pipefail

API_KEYS_FIRST="${API_KEYS:-}"
API_KEY="${API_KEY:-${API_KEYS_FIRST%%,*}}"
API_BASE_URL="${API_BASE_URL:-http://100.69.69.119:8000/api/v1}"

flutter run \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=API_KEY="$API_KEY" \
  "$@"
