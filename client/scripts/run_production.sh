#!/bin/bash
set -euo pipefail

# 프로덕션 환경 실행 스크립트 (릴리즈 빌드)
# API_BASE_URL: 실제 운영 HTTPS 백엔드가 준비된 후 명시적으로 지정
# API_KEY: 반드시 환경 변수로 지정 필요
API_KEY="${API_KEY:?API_KEY 환경 변수를 설정하세요}"
API_BASE_URL="${API_BASE_URL:?API_BASE_URL 환경 변수를 실제 운영 HTTPS URL로 설정하세요}"

flutter run --release \
  --dart-define=ENV=production \
  --dart-define=API_BASE_URL="$API_BASE_URL" \
  --dart-define=API_KEY="$API_KEY"
