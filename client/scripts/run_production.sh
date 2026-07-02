#!/bin/bash
set -euo pipefail

# 프로덕션 환경 실행 스크립트 (릴리즈 빌드)
# API_BASE_URL: 실제 운영 HTTPS 백엔드가 준비된 후 명시적으로 지정
# API_KEY: 반드시 환경 변수로 지정 필요
API_KEY="${API_KEY:?API_KEY 환경 변수를 설정하세요}"
API_BASE_URL="${API_BASE_URL:?API_BASE_URL 환경 변수를 실제 운영 HTTPS URL로 설정하세요}"
API_HEALTH_URL="${API_HEALTH_URL:-${API_BASE_URL%/}/health}"
API_HEALTH_TIMEOUT="${API_HEALTH_TIMEOUT:-10}"

if [[ "$API_BASE_URL" != https://* ]]; then
  echo "API_BASE_URL은 프로덕션에서 반드시 HTTPS URL이어야 합니다: $API_BASE_URL" >&2
  exit 1
fi

if [[ "${SKIP_API_HEALTH_CHECK:-false}" != "true" ]]; then
  if ! curl --fail --silent --show-error --max-time "$API_HEALTH_TIMEOUT" "$API_HEALTH_URL" >/dev/null; then
    echo "프로덕션 API health check 실패: $API_HEALTH_URL" >&2
    echo "DNS/HTTPS/backend 배포를 먼저 완료한 뒤 다시 실행하세요." >&2
    exit 1
  fi
fi

flutter run --release \
  --dart-define=ENV=production \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=API_KEY="$API_KEY"
